import io
import zipfile
from datetime import timedelta

from crawlops.db import Session
from crawlops.models import Job, Schedule, now
from crawlops.services import dispatch_due


def run_spec(ready, **kw):
    return {"deployment_id": ready["deployment"]["id"], "spider": "catalog", **kw}


def test_project_crud(client, auth):
    r = client.post("/api/projects", json={"name": "one"}, headers=auth)
    assert r.status_code == 201
    id = r.json()["id"]
    assert client.get("/api/projects", headers=auth).json()["total"] == 1
    assert (
        client.patch(
            "/api/projects/" + id, json={"name": "two", "description": "updated"}, headers=auth
        ).json()["name"]
        == "two"
    )
    assert client.delete("/api/projects/" + id, headers=auth).status_code == 200
    assert client.get("/api/projects/" + id, headers=auth).status_code == 404


def test_auth_and_rbac(client, auth, viewer):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json={"name": "bad"}, headers=viewer).status_code == 403
    assert client.get("/api/projects", headers=viewer).status_code == 200
    assert client.post("/internal/jobs/claim?host_id=bad", headers=auth).status_code == 401
    assert client.get("/api/audit", headers=viewer).status_code == 403


def test_deployment_discovery_and_activation(client, auth, ready):
    dep_id = ready["deployment"]["id"]
    detail = client.get("/api/deployments/" + dep_id, headers=auth).json()
    assert detail["status"] == "READY"
    assert detail["spiders"] == ["catalog"]
    assert detail["artifact"]["image_id"].startswith("sha256:")
    assert client.post(f"/api/deployments/{dep_id}/activate", headers=auth).status_code == 200
    project = client.get("/api/projects/" + ready["project"]["id"], headers=auth).json()
    assert project["active_deployment_id"] == dep_id


def test_job_validation_and_idempotency(client, auth, ready):
    headers = {**auth, "Idempotency-Key": "same-request"}
    spec = run_spec(ready)
    one = client.post("/api/jobs", json=spec, headers=headers)
    two = client.post("/api/jobs", json=spec, headers=headers)
    assert one.status_code == 201
    assert one.json()["id"] == two.json()["id"]
    assert client.get("/api/jobs", headers=auth).json()["total"] == 1
    assert client.post("/api/jobs", json={**spec, "spider": "missing"}, headers=auth).status_code == 422
    assert (
        client.post(
            "/api/jobs", json={**spec, "settings": {"EXTENSIONS": "malicious"}}, headers=auth
        ).status_code
        == 422
    )


def test_worker_resume_completion_and_durable_logs(client, auth, ready, host, agent_auth):
    job = client.post("/api/jobs", json=run_spec(ready), headers=auth).json()
    path = "/internal/jobs/claim?host_id=" + host["id"]
    first = client.post(path, headers=agent_auth).json()
    second = client.post(path, headers=agent_auth).json()
    assert first["attempt"]["id"] == second["attempt"]["id"]
    id = first["attempt"]["id"]
    base = f"/internal/attempts/{id}"
    params = {"host_id": host["id"]}
    assert (
        client.post(
            base + "/update",
            params=params,
            json={"status": "RUNNING", "container_id": "container"},
            headers=agent_auth,
        ).status_code
        == 200
    )
    chunk = {"sequence": 0, "text": "2026-01-01 INFO hello\n"}
    for _ in range(2):
        assert client.post(base + "/log", params=params, json=chunk, headers=agent_auth).status_code == 200
    done = {
        "status": "SUCCEEDED",
        "exit_code": 0,
        "statistics": {"item_scraped_count": 3, "finish_reason": "finished"},
    }
    for _ in range(2):
        assert (
            client.post(base + "/complete", params=params, json=done, headers=agent_auth).status_code == 200
        )
    detail = client.get("/api/jobs/" + job["id"], headers=auth).json()
    assert detail["status"] == "SUCCEEDED"
    assert detail["attempts"][0]["statistics"]["item_scraped_count"] == 3
    assert len(client.get(f"/api/logs/attempt/{id}", headers=auth).json()) == 1
    assert "hello" in client.get(f"/api/logs/attempt/{id}/download", headers=auth).text
    assert client.post(path, headers=agent_auth).json() is None


def test_cancel_race_and_retry(client, auth, ready, host, agent_auth):
    job = client.post("/api/jobs", json=run_spec(ready), headers=auth).json()
    assert client.post(f"/api/jobs/{job['id']}/cancel", headers=auth).json()["status"] == "CANCELLED"
    job = client.post("/api/jobs", json=run_spec(ready, max_retries=1, retry_delay=1), headers=auth).json()
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    id = claim["attempt"]["id"]
    r = client.post(
        f"/internal/attempts/{id}/complete",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"status": "FAILED", "exit_code": 1},
    )
    assert r.json()["status"] == "QUEUED"
    with Session() as db:
        db.get(Job, job["id"]).requested_at = now() - timedelta(seconds=1)
        db.commit()
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    assert claim["attempt"]["number"] == 1
    id = claim["attempt"]["id"]
    client.post(f"/api/jobs/{job['id']}/cancel", headers=auth)
    r = client.post(
        f"/internal/attempts/{id}/complete",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"status": "SUCCEEDED", "exit_code": 0},
    )
    assert r.json()["status"] == "CANCELLED"


def test_worker_callback_ownership(client, auth, ready, host, agent_auth):
    client.post("/api/jobs", json=run_spec(ready), headers=auth)
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    id = claim["attempt"]["id"]
    r = client.post(
        f"/internal/attempts/{id}/complete?host_id=other", json={"status": "FAILED"}, headers=agent_auth
    )
    assert r.status_code == 409


def test_schedule_persistence_duplicate_dispatch(client, auth, ready):
    r = client.post(
        "/api/schedules",
        json={**run_spec(ready), "name": "every-minute", "cron": "* * * * *", "timezone": "Asia/Kolkata"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    id = r.json()["id"]
    with Session() as db:
        db.get(Schedule, id).next_run_at = now() - timedelta(seconds=1)
        db.commit()
    # New sessions simulate service restarts; unique occurrence keys and atomic advancement persist.
    with Session() as db:
        assert dispatch_due(db) == 1
    with Session() as db:
        assert dispatch_due(db) == 0
    jobs = client.get("/api/jobs?schedule_id=" + id, headers=auth).json()
    assert jobs["total"] == 1
    assert jobs["items"][0]["trigger"] == "schedule"
    assert client.get("/api/schedules", headers=auth).json()["total"] == 1


def test_schedule_overlap_and_preview(client, auth, ready):
    spec = {**run_spec(ready), "name": "daily", "cron": "0 6 * * *", "timezone": "America/New_York"}
    preview = client.post("/api/schedules/preview", json=spec, headers=auth)
    assert len(preview.json()["next"]) == 5
    r = client.post("/api/schedules", json=spec, headers=auth)
    id = r.json()["id"]
    for _ in range(2):
        with Session() as db:
            db.get(Schedule, id).next_run_at = now() - timedelta(seconds=1)
            db.commit()
        with Session() as db:
            dispatch_due(db)
    assert client.get("/api/jobs?schedule_id=" + id, headers=auth).json()["total"] == 1


def test_archive_upload_and_build_claim(client, auth, agent_auth):
    p = client.post("/api/projects", json={"name": "archive"}, headers=auth).json()
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as z:
        z.writestr("nested/scrapy.cfg", "[settings]\ndefault = demo.settings\n")
        z.writestr("nested/demo/settings.py", "SPIDER_MODULES = ['demo.spiders']")
    r = client.post(
        f"/api/projects/{p['id']}/deployments/archive",
        headers=auth,
        data={"version": "v1"},
        files={"file": ("project.zip", content.getvalue(), "application/zip")},
    )
    assert r.status_code == 202, r.text
    claim = client.post("/internal/builds/claim?agent_id=builder", headers=agent_auth).json()
    assert claim["status"] == "BUILDING"
    assert (
        client.get(f"/internal/builds/{claim['id']}/archive?agent_id=builder", headers=agent_auth).content
        == content.getvalue()
    )
    assert (
        client.get(f"/internal/builds/{claim['id']}/archive?agent_id=other", headers=agent_auth).status_code
        == 409
    )


def test_secret_encryption_and_redaction(client, auth, ready, host, agent_auth):
    r = client.post(
        "/api/environments", json={"name": "prod", "secrets": {"PASSWORD": "sensitive-value"}}, headers=auth
    )
    assert r.status_code == 201, r.text
    env = r.json()
    assert "sensitive-value" not in str(client.get("/api/environments", headers=auth).json())
    client.post("/api/jobs", json=run_spec(ready, environment_id=env["id"]), headers=auth)
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    assert claim["environment"]["PASSWORD"] == "sensitive-value"
    id = claim["attempt"]["id"]
    client.post(
        f"/internal/attempts/{id}/log",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"sequence": 0, "text": "oops sensitive-value"},
    )
    result = client.get(f"/api/logs/attempt/{id}", headers=auth).json()
    assert result[0]["text"] == "oops [REDACTED]"


def test_success_criteria(client, auth, ready, host, agent_auth):
    client.post("/api/jobs", json=run_spec(ready, criteria={"min_items": 10}), headers=auth)
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    id = claim["attempt"]["id"]
    r = client.post(
        f"/internal/attempts/{id}/complete",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"status": "SUCCEEDED", "exit_code": 0, "statistics": {"item_scraped_count": 2}},
    )
    assert r.json()["status"] == "FAILED"
    job = client.get(f"/api/jobs/{claim['job']['id']}", headers=auth).json()
    assert job["attempts"][-1]["failure_reason"] == "Scraped 2 items; minimum required: 10"


def test_error_criteria_explains_zero_exit_failure(client, auth, ready, host, agent_auth):
    job = client.post("/api/jobs", json=run_spec(ready, criteria={"max_errors": 0}), headers=auth).json()
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    result = client.post(
        f"/internal/attempts/{claim['attempt']['id']}/complete",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"status": "SUCCEEDED", "exit_code": 0,
              "statistics": {"item_scraped_count": 3, "log_count/ERROR": 1, "finish_reason": "finished"}},
    )
    assert result.json()["status"] == "FAILED"
    detail = client.get(f"/api/jobs/{job['id']}", headers=auth).json()
    assert "Scrapy recorded 1 errors; maximum allowed: 0" in detail["attempts"][-1]["failure_reason"]


def test_admin_user_management_and_registry_credentials(client, auth, viewer):
    r = client.post(
        "/api/users",
        headers=auth,
        json={"email": "operator@local", "password": "operator-password-123", "role": "operator"},
    )
    assert r.status_code == 201, r.text
    assert "password_hash" not in r.json()
    assert (
        client.post(
            "/api/users", headers=viewer, json={"email": "bad@local", "password": "long-password-123"}
        ).status_code
        == 403
    )
    r = client.post(
        "/api/registries",
        headers=auth,
        json={"registry": "registry.internal:5000", "username": "robot", "password": "registry-secret"},
    )
    assert r.status_code == 201, r.text
    assert "registry-secret" not in str(client.get("/api/registries", headers=auth).json())


def test_disconnected_worker_mark_lost_and_late_completion(client, auth, ready, host, agent_auth):
    from crawlops.models import ExecutionHost

    job = client.post("/api/jobs", headers=auth, json=run_spec(ready)).json()
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    assert client.post(f"/api/jobs/{job['id']}/mark-lost", headers=auth).status_code == 409
    with Session() as db:
        db.get(ExecutionHost, host["id"]).heartbeat_at = now() - timedelta(seconds=120)
        db.commit()
    assert client.post(f"/api/jobs/{job['id']}/mark-lost", headers=auth).json()["status"] == "LOST"
    r = client.post(
        f"/internal/attempts/{claim['attempt']['id']}/complete",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"status": "SUCCEEDED", "exit_code": 0},
    )
    assert r.json()["status"] == "LOST"


def test_scrapy_timeout_is_terminal(client, auth, ready, host, agent_auth):
    client.post("/api/jobs", headers=auth, json=run_spec(ready))
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    r = client.post(
        f"/internal/attempts/{claim['attempt']['id']}/complete",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"status": "FAILED", "exit_code": 1, "statistics": {"finish_reason": "closespider_timeout"}},
    )
    assert r.json()["status"] == "TIMED_OUT"


def test_reused_idempotency_key_rejects_changed_arguments(client, auth, ready):
    headers = {**auth, "Idempotency-Key": "argument-sensitive"}
    assert (
        client.post(
            "/api/jobs", json=run_spec(ready, arguments={"prefix": "first"}), headers=headers
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/jobs", json=run_spec(ready, arguments={"prefix": "changed"}), headers=headers
        ).status_code
        == 409
    )


def test_offline_image_archive_validation(client, auth):
    import json
    import tarfile

    p = client.post("/api/projects", json={"name": "offline"}, headers=auth).json()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as archive:
        payload = json.dumps([{"Config": "config.json", "RepoTags": ["crawler:1"], "Layers": []}]).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    r = client.post(
        f"/api/projects/{p['id']}/deployments/image-archive",
        headers=auth,
        data={"version": "v1"},
        files={"file": ("image.tar", buf.getvalue())},
    )
    assert r.status_code == 202, r.text
    assert r.json()["source"] == "image_archive"
    r = client.post(
        f"/api/projects/{p['id']}/deployments/image-archive",
        headers=auth,
        data={"version": "v2"},
        files={"file": ("bad.tar", b"not a tar")},
    )
    assert r.status_code == 422


def test_retention_keeps_active_logs(client, auth, ready, host, agent_auth):
    from crawlops.maintenance import cleanup
    from crawlops.models import JobLogMetadata

    client.post("/api/jobs", headers=auth, json=run_spec(ready))
    claim = client.post("/internal/jobs/claim", params={"host_id": host["id"]}, headers=agent_auth).json()
    id = claim["attempt"]["id"]
    with Session() as db:
        db.add(
            JobLogMetadata(
                owner_id=id,
                stream="attempt",
                sequence=0,
                text="active",
                created_at=now() - timedelta(days=60),
            )
        )
        db.commit()
        assert cleanup(db)["log_chunks_removed"] == 0
    client.post(
        f"/internal/attempts/{id}/complete",
        params={"host_id": host["id"]},
        headers=agent_auth,
        json={"status": "FAILED", "exit_code": 1},
    )
    with Session() as db:
        assert cleanup(db)["log_chunks_removed"] == 1
