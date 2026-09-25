"""站内活动/专题页测试：admin CRUD + 公开详情。"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestActivityAdmin:
    async def test_create_and_public_get(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/activities", headers=console_headers, json={
            "title": "周末观影活动", "summary": "一起看电影", "content": "活动正文",
            "location": "大学生活动中心", "status": 1,
        })
        assert r.status_code == 200, r.text
        aid = r.json()["data"]["id"]

        r = await client.get(f"/api/v1/activities/{aid}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["title"] == "周末观影活动"
        assert data["content"] == "活动正文"

    async def test_list_and_search(self, client: AsyncClient, console_headers: dict):
        await client.post("/api/v1/admin/activities", headers=console_headers, json={
            "title": "篮球赛", "content": "正文", "status": 1,
        })
        await client.post("/api/v1/admin/activities", headers=console_headers, json={
            "title": "读书会", "content": "正文", "status": 0,
        })
        r = await client.get("/api/v1/admin/activities?q=篮球", headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["title"] == "篮球赛"

    async def test_update_and_down_404(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/activities", headers=console_headers, json={
            "title": "临时活动", "content": "正文", "status": 1,
        })
        aid = r.json()["data"]["id"]

        r = await client.put(f"/api/v1/admin/activities/{aid}", headers=console_headers, json={
            "title": "临时活动·改", "status": 0,
        })
        assert r.status_code == 200

        r = await client.get(f"/api/v1/activities/{aid}")
        assert r.status_code == 404

    async def test_delete_activity(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/activities", headers=console_headers, json={
            "title": "待删除", "content": "正文", "status": 1,
        })
        aid = r.json()["data"]["id"]
        r = await client.delete(f"/api/v1/admin/activities/{aid}", headers=console_headers)
        assert r.status_code == 200

        r = await client.get(f"/api/v1/activities/{aid}")
        assert r.status_code == 404
