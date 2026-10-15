from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter
from fastapi import HTTPException
from sqlalchemy import func, select

from .models import Deployment, Job, JobAttempt, Schedule, Spider, now
from .schemas import RunInput
from .security import aware
from .state import ACTIVE


def next_cron(expression, zone, after):
    return (
        croniter(expression, aware(after).astimezone(ZoneInfo(zone)))
        .get_next(__import__("datetime").datetime)
        .astimezone(UTC)
    )


def validate_run(db, spec: RunInput):
    dep = db.get(Deployment, spec.deployment_id)
    if not dep or dep.status != "READY":
        raise HTTPException(409, "Deployment is not ready")
    if not db.scalar(select(Spider).where(Spider.deployment_id == dep.id, Spider.name == spec.spider)):
        raise HTTPException(422, "Spider does not exist in this deployment")
    if spec.environment_id:
        from .models import EnvironmentConfiguration

        if not db.get(EnvironmentConfiguration, spec.environment_id):
            raise HTTPException(422, "Environment does not exist")
    return dep


def create_job(db, spec: RunInput, trigger="manual", key=None, schedule_id=None):
    if key:
        existing = db.scalar(select(Job).where(Job.idempotency_key == key))
        if existing:
            if any(getattr(existing, k) != v for k, v in spec.model_dump().items()):
                raise HTTPException(409, "Idempotency key already used for another request")
            return existing
    dep = validate_run(db, spec)
    job = Job(
        project_id=dep.project_id,
        trigger=trigger,
        idempotency_key=key,
        schedule_id=schedule_id,
        **spec.model_dump(),
    )
    db.add(job)
    db.flush()
    return job


def dispatch_due(db, clock=None):
    clock = clock or now()
    due = db.scalars(
        select(Schedule)
        .where(Schedule.enabled.is_(True), Schedule.next_run_at <= clock)
        .order_by(Schedule.next_run_at)
        .with_for_update(skip_locked=True)
        .limit(100)
    ).all()
    dispatched = 0
    for sched in due:
        occurrence = aware(sched.next_run_at)
        # Skip old occurrences, but allow one polling interval of lateness.
        missed = sched.misfire == "skip" and occurrence < clock - timedelta(seconds=60)
        running = db.scalar(
            select(func.count()).select_from(Job).where(Job.schedule_id == sched.id, Job.status.in_(ACTIVE))
        )
        allowed = running < sched.max_concurrent and (sched.overlap == "allow" or running == 0)
        if not missed and allowed:
            key = f"schedule:{sched.id}:{occurrence.isoformat()}"
            create_job(db, RunInput.model_validate(sched.spec), "schedule", key, sched.id)
            dispatched += 1
        if sched.cron:
            sched.next_run_at = next_cron(
                sched.cron, sched.timezone, clock if sched.misfire == "skip" else occurrence
            )
        else:
            sched.enabled = False
    db.commit()
    return dispatched


def attempt_count(db, job_id):
    return db.scalar(select(func.count()).select_from(JobAttempt).where(JobAttempt.job_id == job_id))
