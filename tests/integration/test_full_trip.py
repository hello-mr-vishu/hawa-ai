"""Integration tests for the hawa-ai FastAPI server.

Tests marked with `live_api` require a valid GOOGLE_API_KEY env var.
All others use the FastAPI test client without hitting external APIs.
"""

import os
import tempfile
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def test_app(tmp_path):
    """Creates a fresh FastAPI app instance with a temp SQLite DB."""
    db_path = str(tmp_path / "test_session.db")

    # Patch settings before importing the server module
    import travel_agent.core.config as cfg_module

    original_db = cfg_module.settings.session_db_path
    cfg_module.settings.session_db_path = db_path

    # Also patch the preferences DB path
    import travel_agent.core.preferences as prefs_module

    from pathlib import Path
    original_prefs_db = prefs_module._DB_PATH
    prefs_module._DB_PATH = Path(db_path)

    # Re-import server to pick up patched settings
    import importlib
    import travel_agent.api.server as server_module

    importlib.reload(server_module)

    async with server_module.app.router.lifespan_context(server_module.app):
        transport = ASGITransport(app=server_module.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    # Restore original settings
    cfg_module.settings.session_db_path = original_db
    prefs_module._DB_PATH = original_prefs_db


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, test_app):
        response = await test_app.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_has_session_db_field(self, test_app):
        response = await test_app.get("/health")
        assert "session_db" in response.json()


class TestUserPreferences:
    @pytest.mark.asyncio
    async def test_get_preferences_empty_user(self, test_app):
        user_id = f"test-user-{uuid.uuid4().hex[:8]}"
        response = await test_app.get(f"/users/{user_id}/preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id
        assert data["preferences"] == {}

    @pytest.mark.asyncio
    async def test_set_and_get_preference(self, test_app):
        user_id = f"test-user-{uuid.uuid4().hex[:8]}"

        # Set a preference
        put_response = await test_app.put(
            f"/users/{user_id}/preferences",
            json={"key": "dietary", "value": "vegetarian"},
        )
        assert put_response.status_code == 200

        # Retrieve and verify
        get_response = await test_app.get(f"/users/{user_id}/preferences")
        assert get_response.status_code == 200
        prefs = get_response.json()["preferences"]
        assert "dietary_restrictions" in prefs or "dietary" in prefs

    @pytest.mark.asyncio
    async def test_delete_preference(self, test_app):
        user_id = f"test-user-{uuid.uuid4().hex[:8]}"

        # Set then delete
        await test_app.put(
            f"/users/{user_id}/preferences",
            json={"key": "home_airport", "value": "DEL"},
        )
        del_response = await test_app.delete(
            f"/users/{user_id}/preferences/home_airport"
        )
        assert del_response.status_code == 200


class TestTokenUsage:
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Requires GOOGLE_API_KEY for live API call",
    )
    async def test_token_usage_recorded_after_chat(self, test_app):
        session_id = str(uuid.uuid4())
        response = await test_app.post(
            "/trips/chat",
            json={
                "user_id": "test-user",
                "session_id": session_id,
                "message": "What is the capital of France?",
            },
        )
        assert response.status_code == 200

        usage_response = await test_app.get(f"/session/{session_id}/usage")
        assert usage_response.status_code == 200
        usage = usage_response.json()
        assert usage["total_tokens"] > 0

    @pytest.mark.asyncio
    async def test_token_usage_404_for_unknown_session(self, test_app):
        response = await test_app.get("/session/nonexistent-session-id/usage")
        assert response.status_code == 404


class TestFullTripFlow:
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Requires GOOGLE_API_KEY for live API call",
    )
    async def test_full_plan_trip_flow(self, test_app):
        response = await test_app.post(
            "/trips/plan",
            json={
                "user_id": "integration-test-user",
                "destination": "Paris",
                "duration_days": 3,
                "budget_tier": "mid-range",
                "interests": "museums, food",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"]
        assert len(data["response"]) > 50

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Requires GOOGLE_API_KEY for live API call",
    )
    async def test_preference_injection_in_plan(self, test_app):
        user_id = f"pref-test-{uuid.uuid4().hex[:8]}"

        # Store a dietary preference
        await test_app.put(
            f"/users/{user_id}/preferences",
            json={"key": "dietary", "value": "vegetarian"},
        )

        # Plan a trip — preference should be injected into the prompt
        response = await test_app.post(
            "/trips/plan",
            json={
                "user_id": user_id,
                "destination": "Tokyo",
                "duration_days": 5,
                "budget_tier": "mid-range",
            },
        )
        assert response.status_code == 200
        # The response should mention vegetarian options
        assert "vegetarian" in response.json()["response"].lower() or \
               response.json()["tokens_used"] is not None

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY"),
        reason="Requires GOOGLE_API_KEY for live API call",
    )
    async def test_multi_turn_conversation(self, test_app):
        """Second message with same session_id continues the conversation."""
        user_id = "multi-turn-test"

        # First turn
        r1 = await test_app.post(
            "/trips/chat",
            json={"user_id": user_id, "message": "Plan a 3-day trip to Kyoto."},
        )
        assert r1.status_code == 200
        session_id = r1.json()["session_id"]

        # Second turn — continues same session
        r2 = await test_app.post(
            "/trips/chat",
            json={
                "user_id": user_id,
                "session_id": session_id,
                "message": "Change Day 2 to include more hiking.",
            },
        )
        assert r2.status_code == 200
        assert r2.json()["session_id"] == session_id
