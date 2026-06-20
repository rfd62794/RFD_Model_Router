import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import rfd_model_router.api
from fastapi.testclient import TestClient

from rfd_model_router.api import app

client = TestClient(app)


def test_route_endpoint_returns_completion():
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("hello", "groq", "llama-3.3-70b-versatile", 10, 5)
        response = client.post(
            "/route",
            json={"task_type": "code_transformation", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["completion"] == "hello"
        assert data["provider"] == "groq"
        assert data["model"] == "llama-3.3-70b-versatile"
        assert data["tokens"] == {"input": 10, "output": 5}


def test_route_endpoint_unknown_task_falls_back():
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("fallback", "anthropic", "claude-haiku-4-5-20251001", 1, 1)
        response = client.post(
            "/route",
            json={"task_type": "unknown_task", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-haiku-4-5-20251001"


def test_route_endpoint_with_system_prompt():
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("ok", "anthropic", "claude-sonnet-4-6", 2, 3)
        response = client.post(
            "/route",
            json={
                "task_type": "directive",
                "messages": [{"role": "user", "content": "hi"}],
                "system_prompt": "sys",
            },
        )
        assert response.status_code == 200
        kwargs = mock_route.call_args.kwargs
        assert kwargs["system_prompt"] == "sys"


def test_route_endpoint_log_failure_does_not_fail():
    with patch("rfd_model_router.api.route") as mock_route, patch(
        "rfd_model_router.api.log_request"
    ) as mock_log:
        mock_route.return_value = ("ok", "groq", "llama", 1, 1)
        mock_log.side_effect = Exception("log failed")
        response = client.post(
            "/route",
            json={"task_type": "code_transformation", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 200
        assert response.json()["completion"] == "ok"


def test_route_endpoint_invalid_request_returns_422():
    response = client.post("/route", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 422


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_has_providers():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    for provider in ["anthropic", "groq", "gemini", "openrouter"]:
        assert provider in data["providers"]


def test_usage_returns_200():
    response = client.get("/usage")
    assert response.status_code == 200


def test_usage_empty_db():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("rfd_model_router.api.DB_PATH", Path(tmp) / "missing.db"):
            response = client.get("/usage")
            assert response.status_code == 200
            data = response.json()
            assert data["total_requests"] == 0
            assert data["total_input_tokens"] == 0
            assert data["total_output_tokens"] == 0
            assert data["by_task_type"] == {}
            assert data["by_provider"] == {}


def test_missing_key_logs_warning():
    with patch("rfd_model_router.api.os.getenv", return_value=None), patch(
        "rfd_model_router.api.logging.warning"
    ) as mock_warning, patch("rfd_model_router.api.rotate_old_logs"), patch(
        "rfd_model_router.api.init_db"
    ):
        import asyncio
        import rfd_model_router.api

        async def _run():
            async with rfd_model_router.api.lifespan(None):
                pass

        asyncio.run(_run())
        assert mock_warning.called


def test_all_keys_present_no_warning():
    with patch("rfd_model_router.api.os.getenv", return_value="dummy"), patch(
        "rfd_model_router.api.logging.warning"
    ) as mock_warning:
        from fastapi.testclient import TestClient
        from rfd_model_router.api import app

        TestClient(app)
        mock_warning.assert_not_called()


def test_log_rotation_deletes_old_rows():
    db_path = Path(tempfile.gettempdir()) / "rfd_model_router_test_rotate.db"
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                duration_ms INTEGER,
                success INTEGER NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO requests (timestamp, task_type, provider, model, input_tokens, output_tokens, duration_ms, success) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2025-01-01T00:00:00Z", "code", "groq", "llama", 1, 1, 1, 1),
                ("2026-06-19T00:00:00Z", "code", "groq", "llama", 1, 1, 1, 1),
            ],
        )
        conn.commit()
    with patch("rfd_model_router.api.DB_PATH", db_path):
        rfd_model_router.api.rotate_old_logs()
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    assert count == 1


def test_log_rotation_keeps_recent_rows():
    db_path = Path(tempfile.gettempdir()) / "rfd_model_router_test_rotate_recent.db"
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                duration_ms INTEGER,
                success INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO requests (timestamp, task_type, provider, model, input_tokens, output_tokens, duration_ms, success) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("2026-06-19T00:00:00Z", "code", "groq", "llama", 1, 1, 1, 1),
        )
        conn.commit()
    with patch("rfd_model_router.api.DB_PATH", db_path):
        rfd_model_router.api.rotate_old_logs()
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    assert count == 1


def test_log_rotation_failure_is_silent():
    with patch("rfd_model_router.api.DB_PATH", Path("/nonexistent/path/requests.db")):
        try:
            rfd_model_router.api.rotate_old_logs()
        except Exception:
            pytest.fail("rotate_old_logs should not raise")


def test_usage_aggregates_correctly():
    db_path = Path(tempfile.gettempdir()) / "rfd_model_router_test_usage.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task_type TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                duration_ms INTEGER,
                success INTEGER NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO requests
            (timestamp, task_type, provider, model, input_tokens, output_tokens, duration_ms, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-01-01T00:00:00Z", "code", "groq", "llama", 10, 5, 100, 1),
                ("2026-01-01T00:00:00Z", "code", "groq", "llama", 20, 10, 200, 1),
                ("2026-01-01T00:00:00Z", "content", "gemini", "flash", 5, 2, 50, 1),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    with patch("rfd_model_router.api.DB_PATH", db_path):
        response = client.get("/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["total_requests"] == 3
        assert data["total_input_tokens"] == 35
        assert data["total_output_tokens"] == 17
        assert data["by_task_type"]["code"]["requests"] == 2
        assert data["by_provider"]["groq"]["requests"] == 2
        assert data["by_provider"]["gemini"]["requests"] == 1
    try:
        db_path.unlink()
    except PermissionError:
        pass
