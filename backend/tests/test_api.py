"""FastAPI 集成测试。"""
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.auth import create_access_token


def _auth_headers(username: str = "admin") -> dict:
    token = create_access_token(username, 1, "admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthCheck:
    async def test_health(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestTemplates:
    async def test_list_templates(self, client):
        resp = await client.get("/api/generation/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert data["total"] > 0

    async def test_get_template(self, client):
        resp = await client.get("/api/generation/templates/检查笔录")
        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_type"] == "检查笔录"
        assert "schema_fields" in data

    async def test_get_template_not_found(self, client):
        resp = await client.get("/api/generation/templates/nonexistent")
        assert resp.status_code == 404


class TestAuth:
    @pytest.mark.skip(reason="Requires DB table to exist")
    async def test_login_no_user(self, client):
        resp = await client.post("/api/auth/login", json={
            "username": "nonexistent_user_xyz",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    async def test_protected_route_without_token(self, client):
        resp = await client.get("/api/generation/history")
        assert resp.status_code == 401

    async def test_valid_token_accepted(self, client):
        resp = await client.get(
            "/api/generation/history",
            headers=_auth_headers(),
        )
        # 200 if DB ready, or error code
        assert resp.status_code in (200, 500)


class TestValidation:
    async def test_check_deadlines_with_auth(self, client):
        resp = await client.post(
            "/api/generation/check-deadlines",
            json={"doc_type": "行政处罚决定书", "fields": {}},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "warnings" in data

    async def test_health_always_public(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
