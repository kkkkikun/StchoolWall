"""Jobs are enqueued in the caller's transaction; leases fence stale workers."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job

LEASE_SECONDS = 180


async def enqueue_job(db: AsyncSession, kind: str, payload: dict, dedupe_key: str) -> uuid.UUID:
    job_id = uuid.uuid4()
    result = await db.execute(
        insert(Job).values(id=job_id, kind=kind, payload=payload, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=[Job.dedupe_key]).returning(Job.id)
    )
    created = result.scalar_one_or_none()
    if created:
        return created
    return (await db.execute(select(Job.id).where(Job.dedupe_key == dedupe_key))).scalar_one()


async def claim_job(db: AsyncSession) -> Job | None:
    now = datetime.now(timezone.utc)
    await db.execute(update(Job).where(
        Job.status == "running", Job.lease_until < now, Job.attempts >= Job.max_attempts,
    ).values(status="dead", lease_until=None, lease_token=None, last_error="worker lease expired"))
    job = (await db.execute(select(Job).where(
        Job.attempts < Job.max_attempts,
        or_(and_(Job.status == "pending", Job.available_at <= now),
            and_(Job.status == "running", Job.lease_until < now)),
    ).order_by(Job.available_at, Job.created_at).with_for_update(skip_locked=True).limit(1))).scalar_one_or_none()
    if job is None:
        await db.commit()
        return None
    job.status = "running"
    job.attempts += 1
    job.lease_token = uuid.uuid4()
    job.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    await db.commit()
    return job


async def finish_job(db: AsyncSession, job: Job, error: str | None = None, outcome: str = "succeeded") -> bool:
    values = {"status": outcome, "lease_until": None, "lease_token": None, "last_error": None}
    if error:
        # Provider exceptions may contain credentials or submitted content.
        values.update(status="dead" if job.attempts >= job.max_attempts else "pending",
                      last_error=error[:100],
                      available_at=datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** job.attempts)))
    result = await db.execute(update(Job).where(
        Job.id == job.id, Job.status == "running", Job.lease_token == job.lease_token,
    ).values(**values))
    await db.commit()
    return result.rowcount == 1
