"""crawlop: a small authenticated REST client. Credentials remain in environment variables."""

import argparse
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(
        prog="crawlop", description="CrawlOps container-native Scrapy operations"
    )
    parser.add_argument("--url", default=os.environ.get("CRAWLOPS_URL", "http://localhost:8080"))
    parser.add_argument(
        "--token",
        default=os.environ.get("CRAWLOPS_TOKEN", ""),
        help="Prefer CRAWLOPS_TOKEN to avoid shell history",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    login = commands.add_parser("login")
    login.add_argument("--email", default="admin@crawlops.local")
    deploy = commands.add_parser("deploy")
    deploy.add_argument("path", type=Path)
    deploy.add_argument("--project", required=True)
    deploy.add_argument("--version", default=str(int(time.time())))
    image = commands.add_parser("deploy-image")
    image.add_argument("image")
    image.add_argument("--project", required=True)
    image.add_argument("--version", default=str(int(time.time())))
    for name in ("projects", "spiders", "jobs", "schedules"):
        group = commands.add_parser(name)
        sub = group.add_subparsers(dest="action", required=True)
        ls = sub.add_parser("list")
        if name == "spiders":
            ls.add_argument("project")
        if name == "projects":
            create = sub.add_parser("create")
            create.add_argument("name")
            create.add_argument("--description", default="")
        if name == "jobs":
            logs = sub.add_parser("logs")
            logs.add_argument("id")
            logs.add_argument("--follow", action="store_true")
            for action in ("cancel", "rerun"):
                task = sub.add_parser(action)
                task.add_argument("id")
    run = commands.add_parser("run")
    run.add_argument("project")
    run.add_argument("spider")
    run.add_argument("--deployment")
    run.add_argument("--args", default="{}", help="JSON spider arguments")
    run.add_argument("--settings", default="{}", help="JSON settings overrides")
    run.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    with httpx.Client(
        base_url=args.url.rstrip("/") + "/api/",
        timeout=120,
        headers={"Authorization": "Bearer " + args.token},
    ) as client:

        def request(method, path, **kw):
            response = client.request(method, path, **kw)
            if response.is_error:
                raise RuntimeError(f"{response.status_code}: {response.text}")
            return response.json()

        def project(name):
            result = request("GET", "projects", params={"limit": 200})
            match = next((p for p in result["items"] if p["id"] == name or p["name"] == name), None)
            if not match:
                raise RuntimeError("Project not found. Create it with crawlop projects create NAME.")
            return match

        try:
            if args.command == "login":
                import getpass

                result = request(
                    "POST", "auth/login", json={"email": args.email, "password": getpass.getpass()}
                )
                print("Store this token as CRAWLOPS_TOKEN (shown once):")
                print(result["token"])
                return
            if args.command == "projects" and args.action == "create":
                result = request(
                    "POST", "projects", json={"name": args.name, "description": args.description}
                )
            elif args.command in {"deploy", "deploy-image"}:
                p = project(args.project)
                if args.command == "deploy-image":
                    result = request(
                        "POST",
                        f"projects/{p['id']}/deployments/image",
                        json={"reference": args.image, "version": args.version},
                    )
                else:
                    if args.path.is_dir():
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
                            for f in args.path.rglob("*"):
                                if (
                                    f.is_file()
                                    and not f.is_symlink()
                                    and not any(
                                        part in {".git", ".venv", "venv", "__pycache__", "node_modules"}
                                        or part.startswith(".env")
                                        for part in f.relative_to(args.path).parts
                                    )
                                ):
                                    archive.write(f, f.relative_to(args.path))
                        data = buf.getvalue()
                    else:
                        data = args.path.read_bytes()
                    result = request(
                        "POST",
                        f"projects/{p['id']}/deployments/archive",
                        data={"version": args.version},
                        files={"file": ("project.zip", data)},
                    )
            elif args.command in {"run", "spiders"}:
                p = project(args.project)
                dep_id = getattr(args, "deployment", None) or p["active_deployment_id"]
                if not dep_id:
                    raise RuntimeError("Activate a ready deployment first, or pass --deployment for run.")
                if args.command == "spiders":
                    result = request("GET", f"deployments/{dep_id}")["spiders"]
                else:
                    result = request(
                        "POST",
                        "jobs",
                        json={
                            "deployment_id": dep_id,
                            "spider": args.spider,
                            "arguments": json.loads(args.args),
                            "settings": json.loads(args.settings),
                            "timeout": args.timeout,
                        },
                    )
            elif args.command == "jobs" and args.action == "logs":
                cursor = -1
                attempt_id = None
                while True:
                    job = request("GET", f"jobs/{args.id}")
                    if job["attempts"]:
                        attempt = job["attempts"][-1]
                        if attempt_id != attempt["id"]:
                            attempt_id, cursor = attempt["id"], -1
                        rows = request("GET", f"logs/attempt/{attempt_id}", params={"after": cursor})
                        for row in rows:
                            print(row["text"], end="", flush=True)
                            cursor = row["sequence"]
                        if rows:
                            continue
                    if not args.follow or job["status"] in {
                        "SUCCEEDED",
                        "FAILED",
                        "CANCELLED",
                        "TIMED_OUT",
                        "LOST",
                    }:
                        return
                    time.sleep(1)
            elif args.command == "jobs" and args.action in {"cancel", "rerun"}:
                result = request("POST", f"jobs/{args.id}/{args.action}")
            else:
                result = request("GET", args.command, params={"limit": 200})
            print(json.dumps(result, indent=2))
        except (httpx.HTTPError, RuntimeError, ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1) from error


app = main
if __name__ == "__main__":
    main()
