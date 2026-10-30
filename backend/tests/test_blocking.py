"""Mutual blocks affect every authenticated discovery path and reject interaction."""
import pytest
from sqlalchemy import func, select

from app.models.block import UserBlock
from app.models.interaction import Comment
from app.models.post import Post
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


def headers(user):
    return auth_header(create_access_token({"sub": str(user.id), "role": user.role}))


async def seed_posts(student, author):
    async with TestSession() as db:
        rows = [Post(user_id=user.id, post_type="general", content="block regression content",
                     status=1, is_featured=True, like_count=5) for user in (student, author)]
        db.add_all(rows)
        await db.flush()
        db.add(Comment(post_id=rows[0].id, user_id=author.id, content="hidden commenter", status=1))
        await db.commit()
        return [row.id for row in rows]


async def test_block_filters_feeds_search_detail_and_comments(client, student_user, admin_user):
    own, hidden = await seed_posts(student_user, admin_user)
    result = await client.post(f"/api/v1/users/{admin_user.id}/block", headers=headers(student_user))
    assert result.status_code == 200
    for path in ("/api/v1/posts", "/api/v1/posts?order=time", "/api/v1/posts/featured",
                 "/api/v1/posts/hot", "/api/v1/posts/search?q=block"):
        result = await client.get(path, headers=headers(student_user))
        assert result.status_code == 200
        ids = [item["id"] for item in result.json()["data"]["items"]]
        assert hidden not in ids and own in ids
    assert (await client.get(f"/api/v1/posts/{hidden}", headers=headers(student_user))).status_code == 404
    assert (await client.get(f"/api/v1/posts/{own}", headers=headers(admin_user))).status_code == 404
    comments = await client.get(f"/api/v1/posts/{own}/comments", headers=headers(student_user))
    assert comments.json()["data"]["items"] == []
    # Blocking is authenticated discovery policy; public posts remain public.
    assert (await client.get(f"/api/v1/posts/{hidden}")).status_code == 200


async def test_block_refuses_interaction_in_both_directions(client, student_user, admin_user):
    own, hidden = await seed_posts(student_user, admin_user)
    await client.post(f"/api/v1/users/{admin_user.id}/block", headers=headers(student_user))
    for actor, post_id in ((student_user, hidden), (admin_user, own)):
        for suffix, body in (("like", None), ("favorite", None), ("comments", {"content": "blocked"})):
            result = await client.post(f"/api/v1/posts/{post_id}/{suffix}", json=body, headers=headers(actor))
            assert result.status_code == 403


async def test_block_is_idempotent_and_unblock_restores_discovery(client, student_user, admin_user):
    _, hidden = await seed_posts(student_user, admin_user)
    path = f"/api/v1/users/{admin_user.id}/block"
    for _ in range(2):
        assert (await client.post(path, headers=headers(student_user))).status_code == 200
    async with TestSession() as db:
        assert await db.scalar(select(func.count()).select_from(UserBlock)) == 1
    listing = await client.get("/api/v1/user/blocks", headers=headers(student_user))
    assert [item["id"] for item in listing.json()["data"]["items"]] == [str(admin_user.id)]
    for _ in range(2):
        assert (await client.delete(path, headers=headers(student_user))).status_code == 200
    assert (await client.get(f"/api/v1/posts/{hidden}", headers=headers(student_user))).status_code == 200


async def test_self_block_and_foreign_unblock_do_not_change_relationship(client, student_user, admin_user):
    assert (await client.post(f"/api/v1/users/{student_user.id}/block",
                              headers=headers(student_user))).status_code == 400
    await client.post(f"/api/v1/users/{admin_user.id}/block", headers=headers(student_user))
    await client.delete(f"/api/v1/users/{student_user.id}/block", headers=headers(admin_user))
    async with TestSession() as db:
        assert await db.scalar(select(func.count()).select_from(UserBlock)) == 1
