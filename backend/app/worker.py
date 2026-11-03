"""Run with python -m app.worker; PostgreSQL is the durable job source."""
import argparse
import asyncio
import logging
import signal
import time

from app.config import validate_security_config
from app.database import async_session
from app.services.jobs import claim_job, finish_job
from app.services.moderation import (
    check_comment_moderation, check_media_moderation, check_party_moderation,
    check_post_moderation, check_profile_moderation, ManualReviewRequired, ContentRejected,
)
from app.services.view_counters import flush_post_view_counters

logger = logging.getLogger(__name__)
JOB_TIMEOUT_SECONDS = 120
CLEANUP_INTERVAL_SECONDS = 60
VIEW_FLUSH_INTERVAL_SECONDS = 10


async def dispatch_job(job) -> None:
    handlers = {
        "moderate_post": lambda: check_post_moderation(int(job.payload["post_id"])),
        "moderate_media": lambda: check_media_moderation(job.payload["media_id"]),
        "moderate_comment": lambda: check_comment_moderation(int(job.payload["comment_id"])),
        "moderate_party": lambda: check_party_moderation(int(job.payload["party_id"])),
        "moderate_profile": lambda: check_profile_moderation(job.payload),
    }
    handler = handlers.get(job.kind)
    if handler is None:
        raise ValueError("unknown_job_kind")
    await handler()


async def run_once() -> bool:
    async with async_session() as db:
        job = await claim_job(db)
    if job is None:
        return False
    error = None
    outcome = "succeeded"
    try:
        await asyncio.wait_for(dispatch_job(job), timeout=JOB_TIMEOUT_SECONDS)
    except ManualReviewRequired:
        outcome = "review"
    except ContentRejected:
        outcome = "rejected"
    except Exception as exc:
        error = type(exc).__name__
        logger.warning("job failed id=%s kind=%s error=%s", job.id, job.kind, error)
    async with async_session() as db:
        await finish_job(db, job, error, outcome=outcome)
    return True


async def cleanup() -> None:
    from app.services.media import cleanup_unbound_media
    from app.services.sessions import cleanup_sessions
    from app.services.student_verification import cleanup_expired_verifications
    for action in (
        lambda db: cleanup_expired_verifications(db, limit=200),
        cleanup_unbound_media,
        cleanup_sessions,
    ):
        try:
            async with async_session() as db:
                await action(db)
        except Exception as exc:
            # One unavailable storage provider must not stop unrelated retention jobs.
            logger.error("retention task failed error=%s", type(exc).__name__)



async def run(once: bool = False) -> None:
    validate_security_config()
    if once:
        await run_once()
        return
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    last_cleanup = 0.0
    last_view_flush = 0.0
    while not stop.is_set():
        try:
            if time.monotonic() - last_cleanup >= CLEANUP_INTERVAL_SECONDS:
                try:
                    await cleanup()
                except Exception as exc:
                    logger.error("cleanup failed error=%s", type(exc).__name__)
                last_cleanup = time.monotonic()
            if time.monotonic() - last_view_flush >= VIEW_FLUSH_INTERVAL_SECONDS:
                try:
                    async with async_session() as db:
                        folded = await flush_post_view_counters(db)
                    if folded:
                        logger.info("view counters folded posts=%s", folded)
                except Exception as exc:
                    logger.error("view counter flush failed error=%s", type(exc).__name__)
                last_view_flush = time.monotonic()
            worked = await run_once()
        except Exception as exc:
            logger.error("worker iteration failed error=%s", type(exc).__name__)
            worked = False
        if not worked:
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except asyncio.TimeoutError:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SchoolWall durable moderation worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(once=args.once))
