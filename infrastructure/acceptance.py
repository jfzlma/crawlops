"""Real Docker acceptance test. Run against Compose, never a fake executor.

Usage: CRAWLOPS_PASSWORD=... python infrastructure/acceptance.py --restart
Leaves project/job history intact for inspection; does not delete operator data.
"""

import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timedelta, timezone
import zipfile
import httpx

root = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--restart", action="store_true", help="Verify API, dashboard, and worker restarts")
    args = parser.parse_args()
    password = os.environ.get("CRAWLOPS_PASSWORD")
    if not password:
        import getpass

        password = getpass.getpass("CrawlOps administrator password: ")
    with httpx.Client(base_url=args.url + "/api/", timeout=120) as client:

        def req(method, path, **kw):
            result = client.request(method, path, **kw)
            result.raise_for_status()
            return result.json()

        def wait(path, terminal, timeout=600):
            started = time.monotonic()
            while time.monotonic() - started < timeout:
                try:
                    obj = req("GET", path)
                    if obj["status"] in terminal:
                        return obj
                except (httpx.HTTPError, KeyError):
                    time.sleep(1)
                    continue
                time.sleep(1)
            raise RuntimeError(f"Timed out waiting for {path}")

        login = req(
            "POST",
            "auth/login",
            json={
                "email": os.environ.get("CRAWLOPS_ADMIN_EMAIL", "admin@crawlops.local"),
                "password": password,
            },
        )
        client.headers["Authorization"] = "Bearer " + login["token"]
        p = req(
            "POST",
            "projects",
            json={"name": "acceptance-" + str(int(time.time())), "description": "Real Docker acceptance run"},
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            for f in (root / "examples/simple-spider").rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts:
                    archive.write(f, f.relative_to(root / "examples/simple-spider"))
        dep = req(
            "POST",
            f"projects/{p['id']}/deployments/archive",
            data={"version": "v1"},
            files={"file": ("project.zip", buf.getvalue())},
        )
        dep = wait("deployments/" + dep["id"], {"READY", "FAILED"})
        assert dep["status"] == "READY", dep.get("error")
        assert "catalog" in dep["spiders"]
        build_logs = req("GET", "logs/build/" + dep["build"]["id"])
        assert build_logs, "Missing durable build logs"
        req("POST", f"deployments/{dep['id']}/activate")
        spec = {
            "deployment_id": dep["id"],
            "spider": "catalog",
            "criteria": {"min_items": 3, "max_errors": 0},
        }
        job = req("POST", "jobs", json={**spec, "arguments": {"prefix": "first"}})
        finished = wait("jobs/" + job["id"], {"SUCCEEDED", "FAILED", "TIMED_OUT", "LOST"})
        assert finished["status"] == "SUCCEEDED", finished
        assert finished["attempts"][-1]["statistics"]["item_scraped_count"] == 3
        assert finished["attempts"][-1]["container_id"]
        assert req("GET", "logs/attempt/" + finished["attempts"][-1]["id"])
        second = req("POST", "jobs", json={**spec, "arguments": {"prefix": "second", "delay": "2"}})
        active = wait("jobs/" + second["id"], {"RUNNING", "SUCCEEDED", "FAILED"})
        if args.restart:
            assert active["status"] == "RUNNING", "Expected slow fixture spider to remain running"
            subprocess.run(["docker", "compose", "restart", "worker", "api", "web"], cwd=root, check=True)
        second = wait("jobs/" + second["id"], {"SUCCEEDED", "FAILED", "TIMED_OUT", "LOST"})
        assert second["status"] == "SUCCEEDED", second
        assert len(second["attempts"]) == 1, "Worker restart created duplicate attempts"
        assert req("GET", "jobs/" + job["id"])["status"] == "SUCCEEDED"
        image = req(
            "POST",
            f"projects/{p['id']}/deployments/image",
            json={"version": "existing", "reference": dep["artifact"]["image_id"]},
        )
        image = wait("deployments/" + image["id"], {"READY", "FAILED"})
        assert image["status"] == "READY", image
        scheduled = req(
            "POST",
            "schedules",
            json={
                **spec,
                "name": "acceptance once",
                "run_at": (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat(),
            },
        )
        if args.restart:
            subprocess.run(["docker", "compose", "restart", "scheduler"], cwd=root, check=True)
        time.sleep(15)
        scheduled_jobs = req("GET", "jobs", params={"schedule_id": scheduled["id"]})
        assert scheduled_jobs["total"] == 1, scheduled_jobs
        result = wait("jobs/" + scheduled_jobs["items"][0]["id"], {"SUCCEEDED", "FAILED"})
        assert result["status"] == "SUCCEEDED", result
        print(
            json.dumps(
                {
                    "result": "PASS",
                    "project": p["id"],
                    "deployment": dep["id"],
                    "job": job["id"],
                    "schedule": scheduled["id"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
