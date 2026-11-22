"""The health endpoint must answer even when nothing external is configured."""
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def client_with(**overrides) -> TestClient:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, ollama_host="http://127.0.0.1:9", **overrides  # port 9: nothing listens
    )
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_health_ok_with_nothing_configured():
    resp = client_with().get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == {"configured": False, "ok": False, "detail": "not_configured"}
    assert body["llm"]["ollama"]["reachable"] is False
    assert body["llm"]["gemini"]["configured"] is False


def test_health_reports_the_routing_table():
    body = client_with().get("/api/v1/health").json()
    assert body["llm"]["mode"] == "cache_only"
    assert body["llm"]["routes"]["ingestion"] == "gemini"
    assert body["llm"]["routes"]["vision"] == "ollama"
    assert body["llm"]["vision_order"] == ["ollama"]


def test_health_never_leaks_secrets():
    text = client_with(gemini_api_key="super-secret-key", mongodb_uri="mongodb://user:pw@host").get("/api/v1/health").text
    assert "super-secret-key" not in text
    assert "pw@host" not in text
