import json
import sys

from crawlops import cli


def invoke(monkeypatch, client, args):
    class InProcessClient:
        def __init__(self, **kw):
            self.headers = kw["headers"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, path, **kw):
            return client.request(method, "/api/" + path, headers=self.headers, **kw)

    monkeypatch.setattr(cli.httpx, "Client", InProcessClient)
    monkeypatch.setattr(sys, "argv", ["crawlop", *args])
    cli.main()


def test_cli_project_creation(monkeypatch, client, auth, capsys):
    invoke(
        monkeypatch,
        client,
        ["--token", auth["Authorization"].split()[1], "projects", "create", "cli-project"],
    )
    assert json.loads(capsys.readouterr().out)["name"] == "cli-project"
    assert client.get("/api/projects", headers=auth).json()["total"] == 1


def test_cli_run_and_cancel_use_real_apis(monkeypatch, client, auth, ready, capsys):
    id = ready["deployment"]["id"]
    assert client.post(f"/api/deployments/{id}/activate", headers=auth).status_code == 200
    token = auth["Authorization"].split()[1]
    invoke(monkeypatch, client, ["--token", token, "run", "catalog", "catalog", "--args", '{"prefix":"cli"}'])
    job = json.loads(capsys.readouterr().out)
    assert job["arguments"] == {"prefix": "cli"}
    invoke(monkeypatch, client, ["--token", token, "jobs", "cancel", job["id"]])
    assert json.loads(capsys.readouterr().out)["status"] == "CANCELLED"
