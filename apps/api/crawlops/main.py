import asyncio
import json
import logging
import tempfile
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from . import models as m
from .archive import extract
from .config import settings
from .db import Session, session
from .logs import logs
from .observability import configure_logging
from .schemas import (
    BuildOptions,
    EnvironmentInput,
    ImageInput,
    LoginInput,
    ProjectInput,
    RegistryInput,
    RunInput,
    ScheduleInput,
    TokenInput,
    UserInput,
)
from .security import (
    admin,
    agent,
    audit,
    aware,
    bootstrap,
    cipher,
    current_user,
    issue_token,
    operator,
    passwords,
)
from .services import attempt_count, create_job, dispatch_due, next_cron, validate_run
from .state import ACTIVE, TERMINAL, transition

logger = logging.getLogger("crawlops")

configure_logging()


@asynccontextmanager
async def lifespan(app):
    Path(settings().data_dir).mkdir(parents=True, exist_ok=True)
    with Session() as db:
        bootstrap(db)
    yield


app = FastAPI(title="CrawlOps", version="0.1.0", lifespan=lifespan)


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Record already exists or is still referenced"})


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def get(db, model, id):
    obj = db.get(model, id)
    if obj is None:
        raise HTTPException(404, "Record not found")
    return obj


def public(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def page(db, model, offset=0, limit=50, conditions=()):
    query = select(model).where(*conditions).order_by(model.created_at.desc())
    return {
        "items": [public(x) for x in db.scalars(query.offset(offset).limit(limit))],
        "total": db.scalar(select(func.count()).select_from(model).where(*conditions)),
        "offset": offset,
        "limit": limit,
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "crawlops-api"}


@app.get("/ready")
def ready(db=Depends(session)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.post("/api/auth/login")
def login(body: LoginInput, db=Depends(session)):
    user = db.scalar(select(m.User).where(m.User.email == body.email))
    if not user or not passwords.verify(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"token": issue_token(db, user), "user": {"email": user.email, "role": user.role}}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


@app.post("/api/auth/logout")
def logout(authorization: str = Header(), db=Depends(session), user=Depends(current_user)):
    from .security import digest

    token = db.scalar(select(m.ApiToken).where(m.ApiToken.digest == digest(authorization.split()[-1])))
    db.delete(token)
    db.commit()
    return {"ok": True}


@app.post("/api/tokens", status_code=201)
def token_create(body: TokenInput, db=Depends(session), user=Depends(operator)):
    return {"token": issue_token(db, user, body.name, permanent=True)}


@app.get("/api/tokens")
def token_list(db=Depends(session), user=Depends(current_user)):
    return [
        {"id": x.id, "name": x.name, "created_at": x.created_at, "expires_at": x.expires_at}
        for x in db.scalars(select(m.ApiToken).where(m.ApiToken.user_id == user.id))
    ]


@app.delete("/api/tokens/{id}")
def token_delete(id: str, db=Depends(session), user=Depends(current_user)):
    token = get(db, m.ApiToken, id)
    if token.user_id != user.id:
        raise HTTPException(403, "Token belongs to another user")
    db.delete(token)
    db.commit()
    return {"ok": True}


@app.get("/api/overview")
def overview(db=Depends(session), user=Depends(current_user)):
    counts = dict(db.execute(select(m.Job.status, func.count()).group_by(m.Job.status)).all())
    recent = page(db, m.Job, limit=8)["items"]
    workers = db.scalars(select(m.ExecutionHost)).all()
    cutoff = m.now() - timedelta(seconds=45)
    return {
        "projects": db.scalar(select(func.count()).select_from(m.Project)),
        "deployments": db.scalar(
            select(func.count()).select_from(m.Deployment).where(m.Deployment.status == "READY")
        ),
        "jobs": counts,
        "workers": sum(aware(w.heartbeat_at) > cutoff and w.kind == "worker" for w in workers),
        "recent_jobs": recent,
        "activity": page(db, m.AuditEvent, limit=8)["items"],
    }


@app.get("/api/projects")
def project_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(session),
    user=Depends(current_user),
):
    return page(db, m.Project, offset, limit)


@app.post("/api/projects", status_code=201)
def project_create(body: ProjectInput, db=Depends(session), user=Depends(operator)):
    obj = m.Project(**body.model_dump())
    db.add(obj)
    db.flush()
    audit(db, user.email, "project.create", obj.id)
    db.commit()
    return public(obj)


@app.get("/api/projects/{id}")
def project_detail(id: str, db=Depends(session), user=Depends(current_user)):
    return public(get(db, m.Project, id))


@app.patch("/api/projects/{id}")
def project_update(id: str, body: ProjectInput, db=Depends(session), user=Depends(operator)):
    obj = get(db, m.Project, id)
    obj.name, obj.description = body.name, body.description
    audit(db, user.email, "project.update", id)
    db.commit()
    return public(obj)


@app.delete("/api/projects/{id}")
def project_delete(id: str, db=Depends(session), user=Depends(admin)):
    obj = get(db, m.Project, id)
    if db.scalar(select(m.Deployment.id).where(m.Deployment.project_id == id).limit(1)):
        raise HTTPException(409, "Projects with deployment history cannot be deleted")
    db.delete(obj)
    audit(db, user.email, "project.delete", id)
    db.commit()
    return {"ok": True}


@app.get("/api/deployments")
def deployment_list(
    project_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(session),
    user=Depends(current_user),
):
    return page(
        db, m.Deployment, offset, limit, (m.Deployment.project_id == project_id,) if project_id else ()
    )


@app.post("/api/projects/{id}/deployments/image", status_code=202)
def image_deploy(id: str, body: ImageInput, db=Depends(session), user=Depends(operator)):
    get(db, m.Project, id)
    dep = m.Deployment(project_id=id, version=body.version, source="image", image_reference=body.reference)
    db.add(dep)
    db.flush()
    db.add(m.Build(deployment_id=dep.id))
    audit(db, user.email, "deployment.image", dep.id)
    db.commit()
    return public(dep)


@app.post("/api/projects/{id}/deployments/archive", status_code=202)
def archive_deploy(
    id: str,
    file: UploadFile = File(),
    version: str = Form(),
    options: str = Form("{}"),
    db=Depends(session),
    user=Depends(operator),
):
    get(db, m.Project, id)
    if not 1 <= len(version) <= 100:
        raise HTTPException(422, "Version must have 1–100 characters")
    opts = BuildOptions.model_validate_json(options)
    root = Path(settings().data_dir) / "archives"
    root.mkdir(parents=True, exist_ok=True)
    archive_id = m.uid()
    dest = root / archive_id
    total = 0
    try:
        with dest.open("wb") as out:
            while chunk := file.file.read(65536):
                total += len(chunk)
                if total > settings().max_archive_bytes:
                    raise HTTPException(413, "Archive upload exceeds size limit")
                out.write(chunk)
        with tempfile.TemporaryDirectory() as temp:
            extract(dest, Path(temp), settings().max_extract_bytes, settings().max_archive_files)
        dep = m.Deployment(project_id=id, version=version, source="archive")
        db.add(dep)
        db.flush()
        stored_options = opts.model_dump()
        args = stored_options.pop("build_args")
        if args:
            stored_options["encrypted_build_args"] = cipher().encrypt(json.dumps(args).encode()).decode()
        db.add(m.Build(deployment_id=dep.id, archive_path=archive_id, options=stored_options))
        audit(db, user.email, "deployment.archive", dep.id, {"bytes": total})
        db.commit()
        return public(dep)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@app.get("/api/deployments/{id}")
def deployment_detail(id: str, db=Depends(session), user=Depends(current_user)):
    dep = get(db, m.Deployment, id)
    build = db.scalar(select(m.Build).where(m.Build.deployment_id == id))
    artifact = db.get(m.ImageArtifact, dep.image_artifact_id) if dep.image_artifact_id else None
    return {
        **public(dep),
        "build": {**public(build), "options": {"python": build.options.get("python", "3.12")}}
        if build
        else None,
        "artifact": public(artifact) if artifact else None,
        "spiders": [x.name for x in db.scalars(select(m.Spider).where(m.Spider.deployment_id == id))],
    }


@app.post("/api/deployments/{id}/activate")
def activate(id: str, db=Depends(session), user=Depends(operator)):
    dep = get(db, m.Deployment, id)
    if dep.status != "READY":
        raise HTTPException(409, "Only validated deployments can be activated")
    get(db, m.Project, dep.project_id).active_deployment_id = id
    audit(db, user.email, "deployment.activate", id)
    db.commit()
    return public(dep)


@app.get("/api/jobs")
def job_list(
    project_id: str | None = None,
    status: str | None = None,
    schedule_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(session),
    user=Depends(current_user),
):
    cond = []
    if project_id:
        cond.append(m.Job.project_id == project_id)
    if status:
        cond.append(m.Job.status == status)
    if schedule_id:
        cond.append(m.Job.schedule_id == schedule_id)
    return page(db, m.Job, offset, limit, cond)


@app.post("/api/jobs", status_code=201)
def job_create(
    body: RunInput, idempotency_key: str | None = Header(None), db=Depends(session), user=Depends(operator)
):
    if idempotency_key and len(idempotency_key) > 200:
        raise HTTPException(422, "Idempotency key too long")
    obj = create_job(db, body, key=idempotency_key)
    audit(db, user.email, "job.create", obj.id)
    db.commit()
    return public(obj)


@app.get("/api/jobs/{id}")
def job_detail(id: str, db=Depends(session), user=Depends(current_user)):
    obj = get(db, m.Job, id)
    attempts = db.scalars(
        select(m.JobAttempt).where(m.JobAttempt.job_id == id).order_by(m.JobAttempt.number)
    ).all()
    result = []
    for a in attempts:
        stat = db.scalar(select(m.JobStatistics).where(m.JobStatistics.attempt_id == a.id))
        result.append({**public(a), "statistics": stat.values if stat else {}})
    return {**public(obj), "attempts": result}


@app.post("/api/jobs/{id}/cancel")
def job_cancel(id: str, db=Depends(session), user=Depends(operator)):
    obj = db.scalar(select(m.Job).where(m.Job.id == id).with_for_update())
    if not obj:
        raise HTTPException(404, "Job not found")
    if obj.status not in TERMINAL:
        transition(obj, "CANCELLED" if obj.status in {"PENDING", "QUEUED"} else "CANCELLING")
        audit(db, user.email, "job.cancel", id)
        db.commit()
    return public(obj)


@app.post("/api/jobs/{id}/rerun", status_code=201)
def job_rerun(id: str, db=Depends(session), user=Depends(operator)):
    obj = get(db, m.Job, id)
    spec = RunInput.model_validate({k: getattr(obj, k) for k in RunInput.model_fields})
    result = create_job(db, spec, "rerun")
    audit(db, user.email, "job.rerun", result.id, {"previous_job": id})
    db.commit()
    return public(result)


@app.get("/api/logs/{kind}/{id}")
def log_read(
    kind: str, id: str, after: int = Query(-1, ge=-1), db=Depends(session), user=Depends(current_user)
):
    if kind == "build":
        build = get(db, m.Build, id)
        owner = build.id
    elif kind == "attempt":
        owner = get(db, m.JobAttempt, id).id
    else:
        raise HTTPException(404, "Unknown log type")
    return [public(x) for x in logs.read(db, owner, kind, after)]


@app.get("/api/logs/{kind}/{id}/download")
def log_download(kind: str, id: str, db=Depends(session), user=Depends(current_user)):
    get(db, m.Build if kind == "build" else m.JobAttempt, id)

    def chunks():
        cursor = -1
        with Session() as reader:
            while rows := logs.read(reader, id, kind, cursor):
                for row in rows:
                    yield row.text
                    cursor = row.sequence

    return StreamingResponse(
        chunks(),
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="crawlops.log"'},
    )


@app.get("/api/logs/{kind}/{id}/stream")
async def log_stream(kind: str, id: str, after: int = -1, user=Depends(current_user)):
    with Session() as db:
        get(db, m.Build if kind == "build" else m.JobAttempt, id)

    async def events():
        cursor = after
        for _ in range(300):
            with Session() as db:
                rows = logs.read(db, id, kind, cursor)
                for row in rows:
                    cursor = row.sequence
                    yield f"id: {cursor}\ndata: {json.dumps(jsonable_encoder(public(row)))}\n\n"
                owner = db.get(m.Build if kind == "build" else m.JobAttempt, id)
                if owner.status in TERMINAL | {"READY"} and not rows:
                    yield "event: complete\ndata: {}\n\n"
                    return
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/api/schedules")
def schedule_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(session),
    user=Depends(current_user),
):
    return page(db, m.Schedule, offset, limit)


@app.post("/api/schedules/preview")
def preview(body: ScheduleInput, user=Depends(current_user)):
    if not body.cron:
        if not body.run_at or body.run_at.tzinfo is None:
            raise HTTPException(422, "One-time schedules need a timezone-aware run_at")
        return {"next": [body.run_at]}
    times = []
    cursor = m.now()
    for _ in range(5):
        cursor = next_cron(body.cron, body.timezone, cursor)
        times.append(cursor)
    return {"next": times}


@app.post("/api/schedules", status_code=201)
def schedule_create(body: ScheduleInput, db=Depends(session), user=Depends(operator)):
    spec = RunInput.model_validate(body.model_dump())
    validate_run(db, spec)
    if not body.cron and (not body.run_at or body.run_at.tzinfo is None or body.run_at <= m.now()):
        raise HTTPException(422, "One-time schedule requires a future timezone-aware run_at")
    obj = m.Schedule(
        name=body.name,
        deployment_id=body.deployment_id,
        spider=body.spider,
        cron=body.cron,
        timezone=body.timezone,
        next_run_at=next_cron(body.cron, body.timezone, m.now()) if body.cron else body.run_at,
        overlap=body.overlap,
        misfire=body.misfire,
        max_concurrent=body.max_concurrent,
        spec=spec.model_dump(),
    )
    db.add(obj)
    db.flush()
    audit(db, user.email, "schedule.create", obj.id)
    db.commit()
    return public(obj)


@app.patch("/api/schedules/{id}")
def schedule_toggle(id: str, enabled: bool, db=Depends(session), user=Depends(operator)):
    obj = get(db, m.Schedule, id)
    obj.enabled = enabled
    if enabled and obj.cron and aware(obj.next_run_at) < m.now():
        obj.next_run_at = next_cron(obj.cron, obj.timezone, m.now())
    audit(db, user.email, "schedule.toggle", id, {"enabled": enabled})
    db.commit()
    return public(obj)


@app.get("/api/workers")
def worker_list(db=Depends(session), user=Depends(current_user)):
    return [
        {**public(x), "online": aware(x.heartbeat_at) > m.now() - timedelta(seconds=45)}
        for x in db.scalars(select(m.ExecutionHost))
    ]


@app.get("/api/environments")
def env_list(db=Depends(session), user=Depends(current_user)):
    return [
        {
            **public(x),
            "secret_names": list(
                db.scalars(select(m.SecretReference.name).where(m.SecretReference.environment_id == x.id))
            ),
        }
        for x in db.scalars(select(m.EnvironmentConfiguration))
    ]


@app.post("/api/environments", status_code=201)
def env_create(body: EnvironmentInput, db=Depends(session), user=Depends(admin)):
    obj = m.EnvironmentConfiguration(name=body.name, variables=body.variables)
    db.add(obj)
    db.flush()
    for k, v in body.secrets.items():
        db.add(
            m.SecretReference(
                environment_id=obj.id, name=k, encrypted_value=cipher().encrypt(v.encode()).decode()
            )
        )
    audit(db, user.email, "environment.create", obj.id)
    db.commit()
    return {"id": obj.id, "name": obj.name, "variables": obj.variables, "secret_names": list(body.secrets)}


@app.get("/api/audit")
def audits(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(session),
    user=Depends(admin),
):
    return page(db, m.AuditEvent, offset, limit)


# Agents authenticate separately; no public route has Docker credentials.
@app.post("/internal/heartbeat", dependencies=[Depends(agent)])
def heartbeat(body: dict, db=Depends(session)):
    name = str(body.get("name", ""))[:100]
    if not name or body.get("kind") not in {"worker", "builder"}:
        raise HTTPException(422, "Agent name and kind required")
    host = db.scalar(select(m.ExecutionHost).where(m.ExecutionHost.name == name))
    if not host:
        host = m.ExecutionHost(name=name)
        db.add(host)
        db.flush()
    host.kind = body["kind"]
    host.heartbeat_at = m.now()
    host.capacity = body.get("capacity", {})
    host.docker_available = bool(body.get("docker_available"))
    # Keep last heartbeat as well as host state; prune via operator retention task.
    db.add(m.WorkerHeartbeat(host_id=host.id, details=host.capacity))
    db.commit()
    return public(host)


@app.post("/internal/builds/claim", dependencies=[Depends(agent)])
def build_claim(agent_id: str, db=Depends(session)):
    # Same stable agent can resume BUILDING work; never reassign to a different agent automatically.
    build = db.scalar(
        select(m.Build)
        .where(m.Build.agent_id == agent_id, m.Build.status == "BUILDING")
        .order_by(m.Build.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if not build:
        build = db.scalar(
            select(m.Build)
            .where(m.Build.status == "QUEUED")
            .order_by(m.Build.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
    if not build:
        return None
    build.status, build.agent_id, build.heartbeat_at = "BUILDING", agent_id, m.now()
    dep = get(db, m.Deployment, build.deployment_id)
    dep.status = "BUILDING" if dep.source == "archive" else "VALIDATING"
    db.commit()
    result = public(build)
    result["options"] = decoded_build_options(build)
    result["log_sequence"] = db.scalar(
        select(func.max(m.JobLogMetadata.sequence)).where(
            m.JobLogMetadata.owner_id == build.id, m.JobLogMetadata.stream == "build"
        )
    )
    result["registry_auth"] = None
    ref = dep.image_reference or ""
    registry = (
        ref.split("/")[0]
        if "/" in ref
        and ("." in ref.split("/")[0] or ":" in ref.split("/")[0] or ref.startswith("localhost/"))
        else "docker.io"
    )
    credential = db.scalar(select(m.RegistryCredential).where(m.RegistryCredential.registry == registry))
    if credential:
        result["registry_auth"] = {
            "username": credential.username,
            "password": cipher().decrypt(credential.encrypted_password.encode()).decode(),
        }
    return {**result, "deployment": public(dep)}


def decoded_build_options(build):
    options = dict(build.options)
    encrypted = options.pop("encrypted_build_args", None)
    options["build_args"] = json.loads(cipher().decrypt(encrypted.encode())) if encrypted else {}
    return options


def owned_build(db, id, agent_id):
    build = get(db, m.Build, id)
    if build.agent_id != agent_id:
        raise HTTPException(409, "Build belongs to another agent")
    return build


@app.get("/internal/builds/{id}/archive", dependencies=[Depends(agent)])
def build_archive(id: str, agent_id: str, db=Depends(session)):
    build = owned_build(db, id, agent_id)
    if not build.archive_path:
        raise HTTPException(404, "No source archive")
    return FileResponse(Path(settings().data_dir) / "archives" / build.archive_path)


@app.post("/internal/builds/{id}/log", dependencies=[Depends(agent)])
def build_log(id: str, agent_id: str, body: dict, db=Depends(session)):
    build = owned_build(db, id, agent_id)
    msg = str(body["text"])[:65536]
    for val in decoded_build_options(build).get("build_args", {}).values():
        if val:
            msg = msg.replace(val, "[REDACTED]")
    logs.append(db, id, "build", int(body["sequence"]), msg)
    build.heartbeat_at = m.now()
    db.commit()
    return {"ok": True}


@app.post("/internal/builds/{id}/complete", dependencies=[Depends(agent)])
def build_complete(id: str, agent_id: str, body: dict, db=Depends(session)):
    build = owned_build(db, id, agent_id)
    dep = get(db, m.Deployment, build.deployment_id)
    if build.status in {"READY", "FAILED"}:
        return public(dep)
    if body.get("error"):
        build.status = dep.status = "FAILED"
        dep.error = str(body["error"])[:4000]
        for val in decoded_build_options(build).get("build_args", {}).values():
            if val:
                dep.error = dep.error.replace(val, "[REDACTED]")
    else:
        if not str(body.get("image_id", "")).startswith("sha256:") or not body.get("spiders"):
            raise HTTPException(422, "Immutable image ID and discovered spiders required")
        artifact = m.ImageArtifact(
            reference=dep.image_reference or f"crawlops/{dep.id}",
            image_id=body["image_id"],
            digest=body.get("digest"),
            provenance={"deployment": dep.id, "source": dep.source, "engine_id": body.get("engine_id")},
        )
        db.add(artifact)
        db.flush()
        dep.image_artifact_id = artifact.id
        for name in set(body["spiders"]):
            db.add(m.Spider(deployment_id=dep.id, name=name))
        build.status = dep.status = "READY"
    audit(db, agent_id, "build.complete", id, {"status": build.status})
    db.commit()
    return public(dep)


@app.post("/internal/jobs/claim", dependencies=[Depends(agent)])
def job_claim(host_id: str, db=Depends(session)):
    host = db.scalar(select(m.ExecutionHost).where(m.ExecutionHost.id == host_id).with_for_update())
    if not host:
        raise HTTPException(404, "Worker not found")
    if host.kind != "worker" or not host.docker_available:
        raise HTTPException(409, "Worker Docker engine is unavailable")
    # Return any unfinished attempt to its original worker before allocating new work.
    attempt = db.scalar(
        select(m.JobAttempt)
        .where(m.JobAttempt.host_id == host_id, m.JobAttempt.status.in_(ACTIVE))
        .order_by(m.JobAttempt.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if attempt:
        job = get(db, m.Job, attempt.job_id)
    else:
        job = db.scalar(
            select(m.Job)
            .where(m.Job.status == "QUEUED", m.Job.requested_at <= m.now())
            .order_by(m.Job.requested_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        dep = get(db, m.Deployment, job.deployment_id)
        image = get(db, m.ImageArtifact, dep.image_artifact_id)
        if image.provenance.get("engine_id") and image.provenance["engine_id"] != host.capacity.get(
            "engine_id"
        ):
            return None  # Local immutable IDs cannot be dispatched onto another engine.
        if (host.capacity.get("cpu") and job.cpu > host.capacity["cpu"]) or (
            host.capacity.get("memory_bytes") and job.memory_mb * 1024 * 1024 > host.capacity["memory_bytes"]
        ):
            return None
        transition(job, "DISPATCHING")
        attempt = m.JobAttempt(job_id=job.id, host_id=host_id, number=attempt_count(db, job.id))
        db.add(attempt)
        db.flush()
    dep = get(db, m.Deployment, job.deployment_id)
    artifact = get(db, m.ImageArtifact, dep.image_artifact_id)
    env = {}
    secrets = []
    if job.environment_id:
        env = dict(get(db, m.EnvironmentConfiguration, job.environment_id).variables)
        for secret in db.scalars(
            select(m.SecretReference).where(m.SecretReference.environment_id == job.environment_id)
        ):
            value = cipher().decrypt(secret.encrypted_value.encode()).decode()
            env[secret.name] = value
            secrets.append(value)
    db.commit()
    return {
        "job": public(job),
        "attempt": public(attempt),
        "image": artifact.image_id,
        "environment": env,
        "redactions": secrets,
    }


def redact_job_payload(db, job, payload):
    if not job.environment_id:
        return payload
    values = [
        cipher().decrypt(x.encrypted_value.encode()).decode()
        for x in db.scalars(
            select(m.SecretReference).where(m.SecretReference.environment_id == job.environment_id)
        )
    ]

    def clean(value):
        if isinstance(value, str):
            for secret in values:
                if secret:
                    value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {clean(k): clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    return clean(payload)


def owned_attempt(db, id, host_id):
    attempt = db.scalar(select(m.JobAttempt).where(m.JobAttempt.id == id).with_for_update())
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    if attempt.host_id != host_id:
        raise HTTPException(409, "Attempt belongs to another worker")
    job = db.scalar(select(m.Job).where(m.Job.id == attempt.job_id).with_for_update())
    return attempt, job


@app.get("/internal/attempts/{id}", dependencies=[Depends(agent)])
def attempt_control(id: str, host_id: str, db=Depends(session)):
    attempt, job = owned_attempt(db, id, host_id)
    return {"status": job.status, "attempt": public(attempt)}


@app.post("/internal/attempts/{id}/update", dependencies=[Depends(agent)])
def attempt_update(id: str, host_id: str, body: dict, db=Depends(session)):
    attempt, job = owned_attempt(db, id, host_id)
    if attempt.status in TERMINAL:
        return {"status": job.status}
    status = body.get("status")
    if job.status == "CANCELLING":
        return {"status": job.status}
    if status:
        transition(job, status)
        attempt.status = status
        if status == "RUNNING" and not attempt.started_at:
            attempt.started_at = m.now()
    if body.get("container_id"):
        attempt.container_id = body["container_id"]
    if body.get("resources"):
        attempt.resources = body["resources"]
    if "statistics" in body:
        stat = db.scalar(select(m.JobStatistics).where(m.JobStatistics.attempt_id == id))
        if not stat:
            stat = m.JobStatistics(attempt_id=id)
            db.add(stat)
        stat.values = redact_job_payload(db, job, body["statistics"])
        stat.updated_at = m.now()
    db.commit()
    return {"status": job.status}


@app.post("/internal/attempts/{id}/log", dependencies=[Depends(agent)])
def attempt_log(id: str, host_id: str, body: dict, db=Depends(session)):
    attempt, job = owned_attempt(db, id, host_id)
    msg = str(body["text"])[:65536]
    if job.environment_id:
        for secret in db.scalars(
            select(m.SecretReference).where(m.SecretReference.environment_id == job.environment_id)
        ):
            val = cipher().decrypt(secret.encrypted_value.encode()).decode()
            if val:
                msg = msg.replace(val, "[REDACTED]")
    logs.append(db, id, "attempt", int(body["sequence"]), msg)
    db.commit()
    return {"ok": True}


@app.post("/internal/attempts/{id}/complete", dependencies=[Depends(agent)])
def attempt_complete(id: str, host_id: str, body: dict, db=Depends(session)):
    attempt, job = owned_attempt(db, id, host_id)
    if attempt.status in TERMINAL:
        return {"status": job.status}
    status = body.get("status", "FAILED")
    if status not in TERMINAL:
        raise HTTPException(422, "Terminal status required")
    if job.status == "CANCELLING":
        status = "CANCELLED"
    # Success is based on exit status plus optional final Scrapy criteria.
    stats = body.get("statistics", {})
    reasons = []
    if stats.get("finish_reason") == "closespider_timeout" and status != "CANCELLED":
        status = "TIMED_OUT"
    if status == "SUCCEEDED":
        if body.get("exit_code") != 0 or stats.get("finish_reason", "finished") != "finished":
            status = "FAILED"
            reasons.append(
                f"Crawler exited with code {body.get('exit_code')}; "
                f"finish reason: {stats.get('finish_reason', 'finished')}"
            )
        if stats.get("item_scraped_count", 0) < job.criteria.get("min_items", 0):
            status = "FAILED"
            reasons.append(
                f"Scraped {stats.get('item_scraped_count', 0)} items; "
                f"minimum required: {job.criteria['min_items']}"
            )
        if stats.get("log_count/ERROR", 0) > job.criteria.get("max_errors", 2**31):
            status = "FAILED"
            reasons.append(
                f"Scrapy recorded {stats.get('log_count/ERROR', 0)} errors; "
                f"maximum allowed: {job.criteria['max_errors']}. See execution logs for details"
            )
    if job.status in {"DISPATCHING", "STARTING"} and status in {"SUCCEEDED", "TIMED_OUT"}:
        transition(job, "RUNNING")
    transition(job, status)
    attempt.status, attempt.finished_at = status, m.now()
    attempt.exit_code, attempt.failure_reason = (
        body.get("exit_code"),
        redact_job_payload(db, job, body.get("error") or ("; ".join(reasons) if reasons else None)),
    )
    stat = db.scalar(select(m.JobStatistics).where(m.JobStatistics.attempt_id == id))
    if not stat:
        stat = m.JobStatistics(attempt_id=id)
        db.add(stat)
    stat.values, stat.updated_at = redact_job_payload(db, job, stats), m.now()
    if status in {"FAILED", "TIMED_OUT"} and attempt.number < job.max_retries:
        job.status = "QUEUED"  # Explicit retry boundary: the previous attempt remains terminal.
        job.requested_at = m.now() + timedelta(seconds=job.retry_delay * (2**attempt.number))
    audit(db, host_id, "attempt.complete", id, {"status": status})
    db.commit()
    return {"status": job.status}


@app.post("/internal/scheduler/tick", dependencies=[Depends(agent)])
def scheduler_tick(db=Depends(session)):
    return {"dispatched": dispatch_due(db)}


@app.get("/api/registries")
def registry_list(db=Depends(session), user=Depends(admin)):
    return [
        {"id": x.id, "registry": x.registry, "username": x.username}
        for x in db.scalars(select(m.RegistryCredential))
    ]


@app.post("/api/registries", status_code=201)
def registry_create(body: RegistryInput, db=Depends(session), user=Depends(admin)):
    obj = m.RegistryCredential(
        registry=body.registry,
        username=body.username,
        encrypted_password=cipher().encrypt(body.password.encode()).decode(),
    )
    db.add(obj)
    db.flush()
    audit(db, user.email, "registry.create", obj.id)
    db.commit()
    return {"id": obj.id, "registry": obj.registry, "username": obj.username}


@app.delete("/api/registries/{id}")
def registry_delete(id: str, db=Depends(session), user=Depends(admin)):
    obj = get(db, m.RegistryCredential, id)
    db.delete(obj)
    audit(db, user.email, "registry.delete", id)
    db.commit()
    return {"ok": True}


@app.get("/api/users")
def user_list(db=Depends(session), user=Depends(admin)):
    return [{"id": x.id, "email": x.email, "role": x.role} for x in db.scalars(select(m.User))]


@app.post("/api/users", status_code=201)
def user_create(body: UserInput, db=Depends(session), user=Depends(admin)):
    obj = m.User(email=body.email, password_hash=passwords.hash(body.password), role=body.role)
    db.add(obj)
    db.flush()
    audit(db, user.email, "user.create", obj.id, {"role": obj.role})
    db.commit()
    return {"id": obj.id, "email": obj.email, "role": obj.role}


@app.post("/api/jobs/{id}/mark-lost")
def mark_lost(id: str, db=Depends(session), user=Depends(admin)):
    job = db.scalar(select(m.Job).where(m.Job.id == id).with_for_update())
    if not job:
        raise HTTPException(404, "Job not found")
    attempt = db.scalar(
        select(m.JobAttempt)
        .where(m.JobAttempt.job_id == id, m.JobAttempt.status.in_(ACTIVE))
        .with_for_update()
    )
    if not attempt:
        raise HTTPException(409, "No active attempt")
    host = get(db, m.ExecutionHost, attempt.host_id)
    if aware(host.heartbeat_at) > m.now() - timedelta(seconds=60):
        raise HTTPException(409, "Worker is still online; use cancellation")
    transition(job, "LOST")
    attempt.status, attempt.finished_at = "LOST", m.now()
    attempt.failure_reason = "Operator marked attempt lost after worker disconnected"
    audit(db, user.email, "job.mark_lost", id)
    db.commit()
    return public(job)


@app.post("/api/projects/{id}/deployments/image-archive", status_code=202)
def image_archive_deploy(
    id: str, file: UploadFile = File(), version: str = Form(), db=Depends(session), user=Depends(operator)
):
    import tarfile

    get(db, m.Project, id)
    if not 1 <= len(version) <= 100:
        raise HTTPException(422, "Version must have 1–100 characters")
    root = Path(settings().data_dir) / "archives"
    root.mkdir(parents=True, exist_ok=True)
    archive_id = m.uid()
    dest = root / archive_id
    total = 0
    try:
        with dest.open("wb") as out:
            while chunk := file.file.read(65536):
                total += len(chunk)
                if total > 512 * 1024 * 1024:
                    raise HTTPException(413, "Docker image archives are limited to 512 MB")
                out.write(chunk)
        # Accept uncompressed `docker save` files; never extract image layers in the API.
        with tarfile.open(dest, "r:") as archive:
            manifest = archive.getmember("manifest.json")
            if not manifest.isfile() or manifest.size > 1024 * 1024:
                raise HTTPException(422, "Invalid Docker save manifest")
            entries = json.load(archive.extractfile(manifest))
            if not isinstance(entries, list) or len(entries) != 1:
                raise HTTPException(422, "Import an archive containing exactly one image")
        dep = m.Deployment(project_id=id, version=version, source="image_archive")
        db.add(dep)
        db.flush()
        db.add(m.Build(deployment_id=dep.id, archive_path=archive_id))
        audit(db, user.email, "deployment.image_archive", dep.id, {"bytes": total})
        db.commit()
        return public(dep)
    except (tarfile.TarError, KeyError, json.JSONDecodeError) as error:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, "Upload an uncompressed tar created with docker save") from error
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@app.post("/internal/maintenance", dependencies=[Depends(agent)])
def maintenance_tick(db=Depends(session)):
    from .maintenance import cleanup

    return cleanup(db)


@app.get("/internal/builds/{id}", dependencies=[Depends(agent)])
def build_control(id: str, agent_id: str, db=Depends(session)):
    build = owned_build(db, id, agent_id)
    return {"id": build.id, "status": build.status}
