"""Bounded retention. Never deletes logs belonging to active attempts or builds."""

from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select

from .config import settings
from .models import Build, JobAttempt, JobLogMetadata, WorkerHeartbeat, now
from .state import TERMINAL


def cleanup(db):
    cutoff = now() - timedelta(days=settings().log_retention_days)
    terminal_attempts = select(JobAttempt.id).where(JobAttempt.status.in_(TERMINAL))
    terminal_builds = select(Build.id).where(Build.status.in_({"READY", "FAILED"}))
    attempts = db.execute(
        delete(JobLogMetadata).where(
            JobLogMetadata.created_at < cutoff,
            JobLogMetadata.stream == "attempt",
            JobLogMetadata.owner_id.in_(terminal_attempts),
        )
    ).rowcount
    builds = db.execute(
        delete(JobLogMetadata).where(
            JobLogMetadata.created_at < cutoff,
            JobLogMetadata.stream == "build",
            JobLogMetadata.owner_id.in_(terminal_builds),
        )
    ).rowcount
    db.execute(delete(WorkerHeartbeat).where(WorkerHeartbeat.created_at < now() - timedelta(days=7)))
    for build in db.scalars(
        select(Build).where(
            Build.status.in_({"READY", "FAILED"}),
            Build.created_at < now() - timedelta(days=settings().source_retention_days),
            Build.archive_path.is_not(None),
        )
    ):
        (Path(settings().data_dir) / "archives" / build.archive_path).unlink(missing_ok=True)
        build.archive_path = None
    db.commit()
    return {"log_chunks_removed": attempts + builds}
