import os
import tempfile
from pathlib import Path

os.environ["CRAWLOPS_DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp()) / "test.db")
os.environ["CRAWLOPS_ADMIN_PASSWORD"] = "test-admin-password-123"
os.environ["CRAWLOPS_AGENT_TOKEN"] = "test-agent-token"
os.environ["CRAWLOPS_DATA_DIR"] = tempfile.mkdtemp()
os.environ["CRAWLOPS_ENCRYPTION_KEY"] = "tGhU4UqqAWD2A4MLRkPh9Doo2scoQNzIzwkd3Pa8f80="

import pytest
from crawlops.db import Base, Session, engine
from crawlops.main import app
from crawlops.models import User
from crawlops.security import issue_token, passwords
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client):
    result = client.post(
        "/api/auth/login", json={"email": "admin@crawlops.local", "password": "test-admin-password-123"}
    )
    assert result.status_code == 200
    return {"Authorization": "Bearer " + result.json()["token"]}


@pytest.fixture
def agent_auth():
    return {"Authorization": "Bearer test-agent-token"}


@pytest.fixture
def ready(client, auth, agent_auth):
    project = client.post("/api/projects", json={"name": "catalog"}, headers=auth).json()
    dep = client.post(
        f"/api/projects/{project['id']}/deployments/image",
        json={"version": "v1", "reference": "crawler:1"},
        headers=auth,
    ).json()
    build = client.post("/internal/builds/claim?agent_id=builder", headers=agent_auth).json()
    result = client.post(
        f"/internal/builds/{build['id']}/complete?agent_id=builder",
        headers=agent_auth,
        json={"image_id": "sha256:" + "a" * 64, "spiders": ["catalog"]},
    )
    assert result.status_code == 200, result.text
    return {"project": project, "deployment": dep, "build": build}


@pytest.fixture
def host(client, agent_auth):
    return client.post(
        "/internal/heartbeat",
        json={"name": "worker", "kind": "worker", "docker_available": True, "capacity": {"slots": 1}},
        headers=agent_auth,
    ).json()


@pytest.fixture
def viewer(client):
    with Session() as db:
        user = User(email="viewer@local", password_hash=passwords.hash("viewer-password-123"), role="viewer")
        db.add(user)
        db.flush()
        token = issue_token(db, user)
    return {"Authorization": "Bearer " + token}
