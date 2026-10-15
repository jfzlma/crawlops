"""Deploy and verify two real source versions; retain server history and local evidence."""

import argparse
import getpass
import io
import json
import os
import time
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/versioned-spider"


def archive(version):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(SOURCE.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            content = path.read_bytes()
            if path.name == "catalog.py":
                content = content.replace(b'VERSION = "v1"', f'VERSION = "{version}"'.encode())
            zipped.writestr(str(path.relative_to(SOURCE)), content)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--output", type=Path, default=ROOT / "data/version-verification")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = {"url": args.url, "result": "INCOMPLETE", "runs": []}
    with httpx.Client(base_url=args.url.rstrip("/") + "/api/", timeout=120) as client:
        def req(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        def wait(path, terminal):
            deadline = time.monotonic() + 600
            last_status = None
            while time.monotonic() < deadline:
                obj = req("GET", path)
                if obj["status"] != last_status:
                    print(f"{path}: {obj['status']}", flush=True)
                    last_status = obj["status"]
                if obj["status"] in terminal:
                    return obj
                time.sleep(2)
            raise RuntimeError(f"Timed out waiting for {path}")

        token = os.environ.get("CRAWLOPS_TOKEN")
        if not token:
            password = os.environ.get("CRAWLOPS_PASSWORD") or getpass.getpass("CrawlOps password: ")
            token = req("POST", "auth/login", json={
                "email": os.environ.get("CRAWLOPS_ADMIN_EMAIL", "admin@crawlops.local"),
                "password": password,
            })["token"]
        client.headers["Authorization"] = "Bearer " + token
        project = req("POST", "projects", json={
            "name": "version-check-" + str(time.time_ns()),
            "description": "Deterministic v1/v2 deployment and temporary output verification",
        })
        evidence["project"] = project
        print(f"Created project {project['id']}", flush=True)
        try:
            deployments = {}
            for version in ("v1", "v2"):
                payload = archive(version)
                (args.output / f"{version}.zip").write_bytes(payload)
                dep = req("POST", f"projects/{project['id']}/deployments/archive",
                          data={"version": version}, files={"file": (f"{version}.zip", payload)})
                dep = wait("deployments/" + dep["id"], {"READY", "FAILED"})
                evidence[version] = dep
                if dep.get("build"):
                    logs = req("GET", "logs/build/" + dep["build"]["id"])
                    (args.output / f"{version}-build.json").write_text(json.dumps(logs, indent=2))
                assert dep["status"] == "READY", dep
                assert "catalog" in dep["spiders"], dep
                req("POST", f"deployments/{dep['id']}/activate")
                active = req("GET", f"projects/{project['id']}")
                assert active["active_deployment_id"] == dep["id"], active
                deployments[version] = dep
                verify_run(req, wait, args.output, evidence, dep, version, version)
            assert deployments["v1"]["artifact"]["image_id"] != deployments["v2"]["artifact"]["image_id"]
            verify_run(req, wait, args.output, evidence, deployments["v1"], "v1", "v1-after-v2")
            active = req("GET", f"projects/{project['id']}")
            assert active["active_deployment_id"] == deployments["v2"]["id"], active
            evidence["result"] = "PASS"
        finally:
            (args.output / "results.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps({"result": evidence["result"], "project": project["id"],
                      "evidence": str(args.output)}, indent=2))


def verify_run(req, wait, output, evidence, deployment, version, label):
    count = 3 if version == "v1" else 4
    job = req("POST", "jobs", json={
        "deployment_id": deployment["id"], "spider": "catalog",
        "criteria": {"min_items": count, "max_errors": 0},
    })
    finished = wait("jobs/" + job["id"], {"SUCCEEDED", "FAILED", "TIMED_OUT", "LOST", "CANCELLED"})
    evidence["runs"].append({"label": label, "job": finished})
    attempt = finished["attempts"][-1]
    logs = req("GET", "logs/attempt/" + attempt["id"])
    (output / f"{label}-logs.json").write_text(json.dumps(logs, indent=2))
    assert finished["status"] == "SUCCEEDED", finished
    assert attempt["container_id"], attempt
    assert attempt["statistics"]["item_scraped_count"] == count, attempt
    assert attempt["statistics"].get("log_count/ERROR", 0) == 0, attempt
    text = "".join(chunk["text"] for chunk in logs)
    marker = "SAMPLE_RESULT "
    line = next(line.split(marker, 1)[1] for line in text.splitlines() if marker in line)
    result = json.loads(line)
    names = ["Notebook", "Pencil", "Backpack"] + (["Eraser"] if version == "v2" else [])
    assert result == {"version": version, "items": [{"name": name, "version": version} for name in names]}
    print(f"Verified {label}: {count} exact items, temporary file read-back, zero errors", flush=True)


if __name__ == "__main__":
    main()
