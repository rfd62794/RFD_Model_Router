from unittest.mock import patch

from fastapi.testclient import TestClient

from rfd_model_router.api import app
from rfd_model_router.models import OpenAIRequest


def test_openai_endpoint_returns_200():
    client = TestClient(app)
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("Response text", "groq", "llama-3.3-70b-versatile", 10, 5)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "cline",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert response.status_code == 200


def test_openai_response_has_choices():
    client = TestClient(app)
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("Response text", "groq", "llama-3.3-70b-versatile", 10, 5)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "cline",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) == 1
        assert "message" in data["choices"][0]
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Response text"


def test_openai_response_has_usage():
    client = TestClient(app)
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("Response text", "groq", "llama-3.3-70b-versatile", 10, 5)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "cline",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        data = response.json()
        assert "usage" in data
        assert data["usage"]["prompt_tokens"] == 10
        assert data["usage"]["completion_tokens"] == 5
        assert data["usage"]["total_tokens"] == 15


def test_openai_known_model_maps_to_task_type():
    client = TestClient(app)
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("Response text", "groq", "llama-3.3-70b-versatile", 10, 5)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "code_transformation",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        mock_route.assert_called_once()
        call_args = mock_route.call_args
        assert call_args[0][0] == "code_transformation"  # task_type


def test_openai_unknown_model_falls_back_to_cline():
    client = TestClient(app)
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("Response text", "groq", "llama-3.3-70b-versatile", 10, 5)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        mock_route.assert_called_once()
        call_args = mock_route.call_args
        assert call_args[0][0] == "cline"  # Falls back to cline task_type


def test_openai_stream_true_still_returns_full():
    client = TestClient(app)
    with patch("rfd_model_router.api.route") as mock_route:
        mock_route.return_value = ("Response text", "groq", "llama-3.3-70b-versatile", 10, 5)
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "cline",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data  # Full response, not streaming
        assert data["choices"][0]["message"]["content"] == "Response text"
