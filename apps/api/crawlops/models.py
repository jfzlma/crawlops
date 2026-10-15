import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(UTC)


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Role(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(30), primary_key=True)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(ForeignKey("roles.name"), default="admin")


class ApiToken(Identity, Base):
    __tablename__ = "api_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    name: Mapped[str] = mapped_column(String(100), default="session")


class Project(Identity, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    active_deployment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ImageArtifact(Identity, Base):
    __tablename__ = "image_artifacts"
    reference: Mapped[str] = mapped_column(Text)
    image_id: Mapped[str] = mapped_column(String(100))
    digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict] = mapped_column(JSON, default=dict)


class Deployment(Identity, Base):
    __tablename__ = "deployments"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    image_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_artifact_id: Mapped[str | None] = mapped_column(ForeignKey("image_artifacts.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("project_id", "version"),)


class Build(Identity, Base):
    __tablename__ = "builds"
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    archive_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Spider(Identity, Base):
    __tablename__ = "spiders"
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    __table_args__ = (UniqueConstraint("deployment_id", "name"),)


class ExecutionHost(Identity, Base):
    __tablename__ = "execution_hosts"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="worker")
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    capacity: Mapped[dict] = mapped_column(JSON, default=dict)
    docker_available: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkerHeartbeat(Identity, Base):
    __tablename__ = "worker_heartbeats"
    host_id: Mapped[str] = mapped_column(ForeignKey("execution_hosts.id"), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class EnvironmentConfiguration(Identity, Base):
    __tablename__ = "environments"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)


class SecretReference(Identity, Base):
    __tablename__ = "secrets"
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"))
    name: Mapped[str] = mapped_column(String(100))
    encrypted_value: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("environment_id", "name"),)


class Schedule(Identity, Base):
    __tablename__ = "schedules"
    name: Mapped[str] = mapped_column(String(100))
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"))
    spider: Mapped[str] = mapped_column(String(200))
    cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC")
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    overlap: Mapped[str] = mapped_column(String(20), default="forbid")
    misfire: Mapped[str] = mapped_column(String(20), default="skip")
    max_concurrent: Mapped[int] = mapped_column(Integer, default=1)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)


class Job(Identity, Base):
    __tablename__ = "jobs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    deployment_id: Mapped[str] = mapped_column(ForeignKey("deployments.id"))
    spider: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    environment_id: Mapped[str | None] = mapped_column(ForeignKey("environments.id"), nullable=True)
    schedule_id: Mapped[str | None] = mapped_column(ForeignKey("schedules.id"), nullable=True)
    trigger: Mapped[str] = mapped_column(String(30), default="manual")
    idempotency_key: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    timeout: Mapped[int] = mapped_column(Integer, default=3600)
    memory_mb: Mapped[int] = mapped_column(Integer, default=512)
    cpu: Mapped[float] = mapped_column(Float, default=1)
    max_retries: Mapped[int] = mapped_column(Integer, default=0)
    retry_delay: Mapped[int] = mapped_column(Integer, default=30)
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)


class JobAttempt(Identity, Base):
    __tablename__ = "job_attempts"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    host_id: Mapped[str] = mapped_column(ForeignKey("execution_hosts.id"))
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="DISPATCHING")
    container_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resources: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("job_id", "number"),)


class JobStatistics(Identity, Base):
    __tablename__ = "job_statistics"
    attempt_id: Mapped[str] = mapped_column(ForeignKey("job_attempts.id"), unique=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class JobLogMetadata(Identity, Base):
    __tablename__ = "log_chunks"
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    stream: Mapped[str] = mapped_column(String(20))
    sequence: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("owner_id", "stream", "sequence"),)


class AlertRule(Identity, Base):
    __tablename__ = "alert_rules"
    name: Mapped[str] = mapped_column(String(100))
    rule: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationChannel(Identity, Base):
    __tablename__ = "notification_channels"
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))
    encrypted_config: Mapped[str] = mapped_column(Text)


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    actor: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class RegistryCredential(Identity, Base):
    __tablename__ = "registry_credentials"
    registry: Mapped[str] = mapped_column(String(254), unique=True)
    username: Mapped[str] = mapped_column(String(200))
    encrypted_password: Mapped[str] = mapped_column(Text)
