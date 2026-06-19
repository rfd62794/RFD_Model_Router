from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from rfd_model_router.api import app

client = TestClient(app)


def test_route_endpoint_returns_completion():
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("hello", "groq", "llama-3.1-70b-versatile", 10, 5)
        response = client.post(
            "/route",
            json={"task_type": "code_transformation", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["completion"] == "hello"
        assert data["provider"] == "groq"
        assert data["model"] == "llama-3.1-70b-versatile"
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
