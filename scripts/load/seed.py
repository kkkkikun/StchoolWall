"""Seed synthetic users/posts/comments only into an explicit isolated *_loadtest database.
Run from backend/: ENVIRONMENT=test DATABASE_URL=.../schoolwall_loadtest python ../scripts/load/seed.py ...
Never adds an HTTP seed endpoint; token material is written to a private local file.
"""
import argparse
import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))


def validate_target(environment: str, database_url: str) -> None:
    dbname = urlparse(database_url).path.lstrip("/")
    if environment != "test" or not dbname.endswith("_loadtest"):
        raise SystemExit("seeding requires ENVIRONMENT=test and an explicit *_loadtest database")
    if os.environ.get("ALLOW_SYNTHETIC_LOAD_SEED") != "YES_ISOLATED_DATABASE":
        raise SystemExit("set ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE for isolated test data")


async def seed(args):
    from app.config import settings
    validate_target(settings.ENVIRONMENT, settings.DATABASE_URL)
    if not 10 <= args.users <= 20000 or not 100 <= args.posts <= 1000000 or not 0 <= args.comments <= 5000000:
        raise SystemExit("users must be 10..20000; posts 100..1000000; comments 0..5000000")
    if len(settings.JWT_SECRET) < 32:
        raise SystemExit("use an independent test JWT_SECRET with at least 32 characters")
    if args.output.exists():
        raise SystemExit("output already exists; preserve or remove it explicitly")
    from sqlalchemy import insert, select, func, text
    from app.database import async_session, engine
    from app.models.user import User
    from app.models.post import Post
    from app.models.interaction import Comment
    from app.models.session import UserSession
    import hashlib
    import app.models  # register metadata, schema still requires alembic upgrade head
    from app.utils.security import create_access_token
    rng = random.Random(4221)
    now = datetime.now(timezone.utc)
    run = uuid.uuid4().hex[:10]
    users = [{"id": uuid.uuid4(), "openid": f"loadtest_{run}_{i}", "nickname": f"loadtest-{i}",
              "role": "student", "is_verified": True, "verified_until": now + timedelta(days=1), "status": 1} for i in range(args.users)]
    async with async_session() as db:
        if await db.scalar(select(func.count()).select_from(Post)):
            raise SystemExit("loadtest database must have no posts; use a fresh isolated DB")
        await db.execute(insert(User), users)
        for start in range(0, args.posts, 1000):
            batch = [{"user_id": rng.choice(users)["id"], "post_type": rng.choice(["general", "second_hand", "carpool"]),
                      "content": f"synthetic campus loadtest {run} #{i} course book study activity",
                      "images": [], "status": 1 if i % 20 else 0,
                      "created_at": now - timedelta(seconds=rng.randrange(90 * 86400)),
                      "like_count": 0, "comment_count": 0, "view_count": rng.randrange(2000)}
                     for i in range(start, min(args.posts, start + 1000))]
            await db.execute(insert(Post), batch)
        visible_posts = (await db.execute(select(Post.id, Post.created_at).where(Post.status == 1).order_by(Post.id))).all()
        def synthetic_comment(i):
            post = rng.choice(visible_posts[:100] if rng.random() < 0.8 else visible_posts)
            age_seconds = max(1, int((now - post.created_at).total_seconds()))
            return {"user_id": rng.choice(users)["id"], "post_id": post.id,
                    "content": f"synthetic campus comment {run} #{i}", "status": 1,
                    "created_at": now - timedelta(seconds=rng.randrange(age_seconds))}
        for start in range(0, args.comments, 1000):
            batch = [synthetic_comment(i) for i in range(start, min(args.comments, start + 1000))]
            await db.execute(insert(Comment), batch)
        if args.comments:
            await db.execute(text("UPDATE posts SET comment_count = aggregate.n FROM "
                                  "(SELECT post_id, count(*) AS n FROM comments WHERE status = 1 GROUP BY post_id) aggregate "
                                  "WHERE posts.id = aggregate.post_id"))
        # Test-only credentials cover the approved eight-hour soak; never exposed by an API.
        sessions = [{"id": uuid.uuid4(), "user_id": u["id"], "refresh_hash": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                     "client_type": "loadtest", "token_version": 0, "expires_at": now + timedelta(hours=10)}
                    for u in users]
        await db.execute(insert(UserSession), sessions)
        await db.commit()
        post_ids = list((await db.execute(select(Post.id).where(Post.status == 1).order_by(Post.id.desc()).limit(1000))).scalars())
    payload = {"run": run, "expires_at": (now + timedelta(hours=9)).isoformat(), "post_ids": post_ids, "accounts": [
        {"token": create_access_token({"sub": str(u["id"]), "sid": str(session["id"]), "sv": 0, "scope": "user", "role": "student"}, expires_delta=timedelta(hours=9))} for u, session in zip(users, sessions)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(payload, output)
    await engine.dispose()
    print(f"seeded {args.users} synthetic users, {args.posts} posts and {args.comments} comments; credentials saved privately to {args.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--posts", type=int, default=10000)
    parser.add_argument("--comments", type=int, default=50000)
    parser.add_argument("--output", type=Path, default=Path("/tmp/schoolwall-load/accounts.json"))
    asyncio.run(seed(parser.parse_args()))
