"""Tags 模块测试：标签列表、创建、删除、权限控制"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _seed_tag(name: str):
    from app.models.tag import Tag
    async with TestSession() as db:
        tag = Tag(name=name)
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag


# ============================================================
# GET /api/v1/tags — 标签列表
# ============================================================


class TestListTags:

    @pytest.mark.asyncio
    async def test_empty_list(self, client: AsyncClient):
        """无标签时返回空列表"""
        r = await client.get("/api/v1/tags")
        assert r.status_code == 200
        assert r.json()["data"] == []

    @pytest.mark.asyncio
    async def test_list_returns_all_tags(self, client: AsyncClient):
        """返回所有标签"""
        await _seed_tag("高数资料")
        await _seed_tag("一食堂")
        r = await client.get("/api/v1/tags")
        names = [t["name"] for t in r.json()["data"]]
        assert "高数资料" in names
        assert "一食堂" in names

    @pytest.mark.asyncio
    async def test_list_public_no_token(self, client: AsyncClient):
        """标签列表无需 Token"""
        r = await client.get("/api/v1/tags")
        assert r.status_code == 200


# ============================================================
# POST /api/v1/tags — 创建标签
# ============================================================


class TestCreateTag:

    @pytest.mark.asyncio
    async def test_admin_create_tag(self, client: AsyncClient, admin_user: User):
        """admin 创建标签成功"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.post("/api/v1/tags", json={"name": "求职辅导"}, headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "求职辅导"

    @pytest.mark.asyncio
    async def test_duplicate_name_rejected(self, client: AsyncClient, admin_user: User):
        """重复标签名被拒绝"""
        await _seed_tag("已存在")
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.post("/api/v1/tags", json={"name": "已存在"}, headers=auth_header(token))
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_student_cannot_create(self, client: AsyncClient, student_user: User):
        """student 不能创建标签"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post("/api/v1/tags", json={"name": "试试"}, headers=auth_header(token))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_no_token_cannot_create(self, client: AsyncClient):
        """无 Token 不能创建"""
        r = await client.post("/api/v1/tags", json={"name": "试试"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_name_rejected(self, client: AsyncClient, admin_user: User):
        """空标签名被拒绝"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.post("/api/v1/tags", json={"name": ""}, headers=auth_header(token))
        assert r.status_code == 422


# ============================================================
# DELETE /api/v1/tags/{tag_id} — 删除标签
# ============================================================


class TestDeleteTag:

    @pytest.mark.asyncio
    async def test_admin_delete_tag(self, client: AsyncClient, admin_user: User):
        """admin 删除标签成功"""
        tag = await _seed_tag("待删除")
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.delete(f"/api/v1/tags/{tag.id}", headers=auth_header(token))
        assert r.status_code == 200

        # 确认已删除
        r2 = await client.get("/api/v1/tags")
        names = [t["name"] for t in r2.json()["data"]]
        assert "待删除" not in names

    @pytest.mark.asyncio
    async def test_delete_nonexistent_tag(self, client: AsyncClient, admin_user: User):
        """删除不存在的标签返回 404"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.delete("/api/v1/tags/99999", headers=auth_header(token))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_student_cannot_delete(self, client: AsyncClient, student_user: User):
        """student 不能删除标签"""
        tag = await _seed_tag("受保护")
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.delete(f"/api/v1/tags/{tag.id}", headers=auth_header(token))
        assert r.status_code == 403
