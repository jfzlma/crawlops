"""Outbound-only, restart-reconciling Docker agents. No database credentials."""

import json
import logging
import os
import signal
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import docker
import httpx
from docker.errors import ImageNotFound, NotFound

from . import runner
from .archive import dockerfile, extract
from .observability import configure_logging

log = logging.getLogger("crawlops.agent")

configure_logging()
stop = threading.Event()


class Agent:
    def __init__(self, kind):
        self.kind = kind
        self.name = os.environ.get("CRAWLOPS_AGENT_NAME", f"local-{kind}")
        self.http = httpx.Client(
            base_url=os.environ.get("CRAWLOPS_API_URL", "http://api:8000"),
            timeout=30,
            headers={"Authorization": "Bearer " + os.environ["CRAWLOPS_AGENT_TOKEN"]},
        )
        self.docker = docker.from_env(timeout=120)
        self.host_id = None

    def request(self, method, path, **kw):
        response = self.http.request(method, path, **kw)
        response.raise_for_status()
        return response.json()

    def heartbeat(self):
        available = False
        capacity = {}
        try:
            info = self.docker.info()
            available = True
            capacity = {
                "cpu": info.get("NCPU", 0),
                "memory_bytes": info.get("MemTotal", 0),
                "slots": 1,
                "engine_id": info.get("ID"),
                "containers_running": info.get("ContainersRunning", 0),
            }
        except docker.errors.DockerException:
            log.exception("Docker heartbeat failed")
        host = self.request(
            "POST",
            "/internal/heartbeat",
            json={"name": self.name, "kind": self.kind, "docker_available": available, "capacity": capacity},
        )
        self.host_id = host["id"]

    def heartbeat_loop(self):
        while not stop.wait(10):
            try:
                self.heartbeat()
            except (httpx.HTTPError, docker.errors.DockerException):
                log.exception("Heartbeat failed; will reconnect")

    def run(self):
        self.heartbeat()
        self.cleanup_terminal_containers()
        threading.Thread(target=self.heartbeat_loop, daemon=True).start()
        while not stop.is_set():
            try:
                if self.kind == "builder":
                    work = self.request("POST", "/internal/builds/claim", params={"agent_id": self.name})
                    if work:
                        self.build(work)
                else:
                    work = self.request("POST", "/internal/jobs/claim", params={"host_id": self.host_id})
                    if work:
                        self.execute(work)
                if not work:
                    stop.wait(2)
            except Exception:
                # Never mark a job terminal on a transport error. Reconcile its original container next poll.
                log.exception("Agent iteration failed; durable work will be reconciled")
                stop.wait(3)

    def cleanup_terminal_containers(self):
        label = "crawlops.attempt" if self.kind == "worker" else "crawlops.build"
        for container in self.docker.containers.list(all=True, filters={"label": label}):
            id = container.labels.get(label)
            path = f"/internal/attempts/{id}" if self.kind == "worker" else f"/internal/builds/{id}"
            params = {"host_id": self.host_id} if self.kind == "worker" else {"agent_id": self.name}
            response = self.http.get(path, params=params)
            if response.status_code in {404, 409}:
                continue  # Preserve containers whose ownership is unknown or belongs to another worker.
            response.raise_for_status()
            record = response.json()
            status = record["attempt"]["status"] if self.kind == "worker" else record["status"]
            if status in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED", "LOST", "READY"}:
                container.remove(force=True)

    def build(self, work):
        id = work["id"]
        params = {"agent_id": self.name}
        sequence = (work.get("log_sequence") if work.get("log_sequence") is not None else -1) + 1

        def emit(text):
            nonlocal sequence
            self.request(
                "POST", f"/internal/builds/{id}/log", params=params, json={"sequence": sequence, "text": text}
            )
            sequence += 1

        try:
            tag = "crawlops/" + work["deployment_id"] + ":built"
            if work["deployment"]["source"] == "archive":
                try:
                    image = self.docker.images.get(tag)
                    emit("Resuming: found completed content-addressed build.\n")
                except ImageNotFound:
                    with tempfile.TemporaryDirectory() as directory:
                        archive = Path(directory) / "source.archive"
                        response = self.http.get(f"/internal/builds/{id}/archive", params=params)
                        response.raise_for_status()
                        archive.write_bytes(response.content)
                        root = extract(archive, Path(directory) / "source")
                        dockerfile(root, work["options"].get("python", "3.12"))
                        emit("Validated archive. Building isolated project image…\n")
                        for event in self.docker.api.build(
                            path=str(root),
                            tag=tag,
                            rm=True,
                            decode=True,
                            buildargs=work["options"].get("build_args", {}),
                        ):
                            if "error" in event:
                                raise RuntimeError(event["error"])
                            emit(event.get("stream", json.dumps(event) + "\n"))
                        image = self.docker.images.get(tag)
            elif work["deployment"]["source"] == "image_archive":
                emit("Loading offline Docker image archive into the execution engine…\n")
                response = self.http.get(f"/internal/builds/{id}/archive", params=params)
                response.raise_for_status()
                images = self.docker.images.load(response.content)
                if len(images) != 1:
                    raise RuntimeError("Expected exactly one image in Docker archive")
                image = images[0]
            else:
                reference = work["deployment"]["image_reference"]
                emit(f"Resolving image {reference}\n")
                try:
                    image = self.docker.images.get(reference)
                except ImageNotFound:
                    image = self.docker.images.pull(reference, auth_config=work.get("registry_auth"))
            emit(f"Discovering spiders in {image.id}\n")
            name = f"crawlops-discovery-{id}"
            try:
                container = self.docker.containers.get(name)
            except NotFound:
                container = self.docker.containers.create(
                    image.id,
                    ["-m", "scrapy", "list"],
                    entrypoint="python",
                    name=name,
                    labels={"crawlops.build": id},
                    network_disabled=True,
                    read_only=True,
                    user="65532:65532",
                    mem_limit="256m",
                    nano_cpus=1_000_000_000,
                    pids_limit=128,
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges:true"],
                    tmpfs={"/tmp": "rw,nosuid,size=64m"},
                )
            container.reload()
            if container.status == "created":
                container.start()
            result = container.wait(timeout=60)
            output = container.logs().decode(errors="replace")
            emit(output)
            if result["StatusCode"]:
                raise RuntimeError(
                    "Spider discovery failed. Image needs Python, Scrapy, and a valid project working directory."
                )
            discovery_stdout = container.logs(stdout=True, stderr=False).decode(errors="replace")
            spiders = [
                line.strip()
                for line in discovery_stdout.splitlines()
                if line.strip() and __import__("re").fullmatch(r"[A-Za-z0-9_.-]+", line.strip())
            ]
            if not spiders:
                raise RuntimeError("No spiders found in image")
            digests = image.attrs.get("RepoDigests", [])
            self.request(
                "POST",
                f"/internal/builds/{id}/complete",
                params=params,
                json={
                    "image_id": image.id,
                    "engine_id": self.docker.info().get("ID"),
                    "digest": digests[0] if digests else None,
                    "spiders": spiders,
                },
            )
            container.remove(force=True)
        except httpx.HTTPError:
            raise  # Do not turn a callback outage into a build failure.
        except Exception as error:
            msg = str(error)
            sensitive = list(work["options"].get("build_args", {}).values())
            if work.get("registry_auth"):
                sensitive.append(work["registry_auth"]["password"])
            for value in sensitive:
                if value:
                    msg = msg.replace(value, "[REDACTED]")
            log.error("Build failed: %s", msg)
            emit("ERROR: " + msg + "\n")
            self.request("POST", f"/internal/builds/{id}/complete", params=params, json={"error": msg})

    def execute(self, work):
        job, attempt = work["job"], work["attempt"]
        id = attempt["id"]
        params = {"host_id": self.host_id}
        base = f"/internal/attempts/{id}"
        stats = {}
        sent = 0
        timed_out = False
        container = None

        def redact(text):
            for value in work.get("redactions", []):
                if value:
                    text = text.replace(value, "[REDACTED]")
            return text

        try:
            try:
                container = self.docker.containers.get("crawlops-attempt-" + id)
            except NotFound:
                if job["status"] == "CANCELLING":
                    self.request("POST", base + "/complete", params=params, json={"status": "CANCELLED"})
                    return
                if attempt.get("container_id"):
                    self.request(
                        "POST",
                        base + "/complete",
                        params=params,
                        json={"status": "LOST", "error": "Previously created container no longer exists"},
                    )
                    return
                source = Path(runner.__file__).read_text()
                env = {
                    **work["environment"],
                    "CRAWLOPS_SPEC": json.dumps(
                        {
                            "spider": job["spider"],
                            "settings": job["settings"],
                            "arguments": job["arguments"],
                            "timeout": job["timeout"],
                        }
                    ),
                }
                container = self.docker.containers.create(
                    work["image"],
                    ["-u", "-c", source],
                    entrypoint="python",
                    name="crawlops-attempt-" + id,
                    environment=env,
                    labels={"crawlops.attempt": id},
                    user="65532:65532",
                    mem_limit=f"{job['memory_mb']}m",
                    nano_cpus=int(job["cpu"] * 1e9),
                    pids_limit=256,
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges:true"],
                    read_only=True,
                    tmpfs={"/tmp": "rw,nosuid,size=128m"},
                    log_config=docker.types.LogConfig(
                        type="json-file", config={"max-size": "100m", "max-file": "1"}
                    ),
                )
            container.reload()
            self.request(
                "POST",
                base + "/update",
                params=params,
                json={
                    "status": "STARTING" if job["status"] == "DISPATCHING" else None,
                    "container_id": container.id,
                },
            )
            if container.status == "created":
                control = self.request("GET", base, params=params)
                if control["status"] == "CANCELLING":
                    self.request("POST", base + "/complete", params=params, json={"status": "CANCELLED"})
                    container.remove(force=True)
                    return
                container.start()
            self.request("POST", base + "/update", params=params, json={"status": "RUNNING"})
            while not stop.is_set():
                container.reload()
                running = container.status in {"running", "restarting"}
                raw = container.logs(timestamps=True).decode(errors="replace")
                lines = raw.splitlines(keepends=True)
                if running and lines and not lines[-1].endswith("\n"):
                    lines.pop()
                chunks = []
                for line in lines:
                    if "__CRAWLOPS_STATS__" in line:
                        try:
                            stats = json.loads(line.split("__CRAWLOPS_STATS__", 1)[1])
                        except json.JSONDecodeError:
                            log.warning("Malformed project telemetry")
                    chunks.extend(line[i : i + 60000] for i in range(0, len(line), 60000))
                while sent < len(chunks):
                    self.request(
                        "POST",
                        base + "/log",
                        params=params,
                        json={"sequence": sent, "text": redact(chunks[sent])},
                    )
                    sent += 1
                resources = {}
                if running:
                    usage = container.stats(stream=False)
                    resources = {
                        "memory_bytes": usage.get("memory_stats", {}).get("usage", 0),
                        "cpu_total_ns": usage.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0),
                    }
                self.request(
                    "POST",
                    base + "/update",
                    params=params,
                    json={"statistics": stats, "resources": resources},
                )
                control = self.request("GET", base, params=params)
                if control["status"] in {"LOST", "CANCELLED", "FAILED", "TIMED_OUT", "SUCCEEDED"}:
                    container.remove(force=True)
                    return
                if not running:
                    exit_code = container.attrs["State"]["ExitCode"]
                    status = (
                        "CANCELLED"
                        if control["status"] == "CANCELLING"
                        else ("TIMED_OUT" if timed_out else "SUCCEEDED" if exit_code == 0 else "FAILED")
                    )
                    self.request(
                        "POST",
                        base + "/complete",
                        params=params,
                        json={
                            "status": status,
                            "exit_code": exit_code,
                            "statistics": stats,
                            "error": container.attrs["State"].get("Error")
                            or ("OOM killed" if container.attrs["State"].get("OOMKilled") else None),
                        },
                    )
                    container.remove()
                    return
                started = container.attrs["State"]["StartedAt"]
                start_time = datetime.fromisoformat(started[:26] + "+00:00")
                elapsed = (datetime.now(UTC) - start_time).total_seconds()
                if control["status"] == "CANCELLING" or elapsed > job["timeout"]:
                    timed_out = control["status"] != "CANCELLING"
                    container.stop(timeout=10)
                stop.wait(2)
        except docker.errors.APIError as error:
            if error.status_code in {400, 404}:
                self.request(
                    "POST",
                    base + "/complete",
                    params=params,
                    json={"status": "FAILED", "error": redact(str(error))},
                )
                if container is not None:
                    container.remove(force=True)
            else:
                raise
        except (httpx.HTTPError, docker.errors.DockerException):
            # Engine/transport outages leave durable ownership intact for the same agent to reconcile.
            raise
        except Exception as error:
            log.exception("Execution setup failed")
            if container is None:
                self.request(
                    "POST",
                    base + "/complete",
                    params=params,
                    json={"status": "FAILED", "error": redact(str(error))},
                )
            else:
                raise


def main():
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    kind = os.environ.get("CRAWLOPS_AGENT_KIND", "worker")
    while not stop.is_set():
        try:
            Agent(kind).run()
        except Exception:
            log.exception("Agent connection failed")
            stop.wait(3)


if __name__ == "__main__":
    main()
