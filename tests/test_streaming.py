import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rfd_model_router.adapters.anthropic_adapter import AnthropicAdapter
from rfd_model_router.adapters.gemini_adapter import GeminiAdapter
from rfd_model_router.adapters.groq_adapter import GroqAdapter
from rfd_model_router.adapters.openrouter_adapter import OpenRouterAdapter
from rfd_model_router.api import app
from rfd_model_router.models import Message
from rfd_model_router.router import route_stream, ThrottleError, BudgetExceededError
from rfd_model_router.throttle import _throttle


def test_anthropic_stream_yields_chunks():
    adapter = AnthropicAdapter()
    mock_stream = MagicMock()
    mock_stream.text_stream.__iter__ = lambda self: iter(["Hello", " ", "world"])
    mock_final = MagicMock()
    mock_final.usage.input_tokens = 10
    mock_final.usage.output_tokens = 5
    mock_stream.get_final_message.return_value = mock_final
    mock_context = MagicMock()
    mock_context.__enter__ = lambda self: mock_stream
    mock_context.__exit__ = lambda self, *args: None
    adapter.client.messages.stream = MagicMock(return_value=mock_context)

    gen = adapter.stream("claude-3-5-sonnet", [{"role": "user", "content": "Hi"}])
    chunks = list(gen)
    assert chunks == ["Hello", " ", "world"]


def test_groq_stream_yields_chunks():
    adapter = GroqAdapter()
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
    mock_chunk1.usage = None
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock(delta=MagicMock(content=" world"))]
    mock_chunk2.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    mock_response = MagicMock()
    mock_response.__iter__ = lambda self: iter([mock_chunk1, mock_chunk2])
    adapter.client.chat.completions.create = MagicMock(return_value=mock_response)

    gen = adapter.stream("llama-3.3-70b-versatile", [{"role": "user", "content": "Hi"}])
    chunks = list(gen)
    assert chunks == ["Hello", " world"]


def test_gemini_stream_yields_chunks():
    adapter = GeminiAdapter()
    mock_chunk1 = MagicMock()
    mock_chunk1.text = "Hello"
    mock_chunk1.usage_metadata = None
    mock_chunk2 = MagicMock()
    mock_chunk2.text = " world"
    mock_chunk2.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=5)
    adapter.client.models.generate_content_stream = MagicMock(return_value=[mock_chunk1, mock_chunk2])

    gen = adapter.stream("gemini-2.0-flash-exp", [{"role": "user", "content": "Hi"}])
    chunks = list(gen)
    assert chunks == ["Hello", " world"]


def test_openrouter_stream_yields_chunks():
    adapter = OpenRouterAdapter()
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
    mock_chunk1.usage = None
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock(delta=MagicMock(content=" world"))]
    mock_chunk2.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    mock_response = MagicMock()
    mock_response.__iter__ = lambda self: iter([mock_chunk1, mock_chunk2])
    adapter.client.chat.completions.create = MagicMock(return_value=mock_response)

    gen = adapter.stream("anthropic/claude-3.5-sonnet", [{"role": "user", "content": "Hi"}])
    chunks = list(gen)
    assert chunks == ["Hello", " world"]


def test_stream_returns_token_counts():
    adapter = GroqAdapter()
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="Hi"))]
    mock_chunk.usage = MagicMock(prompt_tokens=15, completion_tokens=7)
    mock_response = MagicMock()
    mock_response.__iter__ = lambda self: iter([mock_chunk])
    adapter.client.chat.completions.create = MagicMock(return_value=mock_response)

    gen = adapter.stream("llama-3.3-70b-versatile", [{"role": "user", "content": "Hi"}])
    # Consume all chunks
    chunks = []
    try:
        while True:
            chunks.append(next(gen))
    except StopIteration as e:
        assert e.value == (15, 7)


def test_route_stream_yields_chunks():
    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {},
            "budgets": {},
        }
        with patch("rfd_model_router.router.get_adapter") as mock_get_adapter:
            adapter = GroqAdapter()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Test"))]
            mock_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
            mock_response = MagicMock()
            mock_response.__iter__ = lambda self: iter([mock_chunk])
            adapter.client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_get_adapter.return_value = adapter

            gen = route_stream("default", [{"role": "user", "content": "Hi"}])
            chunks = list(gen)
            assert chunks == ["Test"]


def test_route_stream_logs_on_completion():
    db_path = Path(tempfile.gettempdir()) / "rfd_model_router_test_stream_log.db"
    if db_path.exists():
        db_path.unlink()
    with patch("rfd_model_router.logger.DB_PATH", db_path):
        from rfd_model_router.logger import init_db
        init_db()

    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {},
            "budgets": {},
        }
        with patch("rfd_model_router.router.get_adapter") as mock_get_adapter:
            with patch("rfd_model_router.logger.DB_PATH", db_path):
                adapter = GroqAdapter()
                mock_chunk = MagicMock()
                mock_chunk.choices = [MagicMock(delta=MagicMock(content="Test"))]
                mock_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
                mock_response = MagicMock()
                mock_response.__iter__ = lambda self: iter([mock_chunk])
                adapter.client.chat.completions.create = MagicMock(return_value=mock_response)
                mock_get_adapter.return_value = adapter

                gen = route_stream("default", [{"role": "user", "content": "Hi"}])
                list(gen)

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    assert count == 1
    try:
        db_path.unlink()
    except PermissionError:
        pass


def test_route_stream_throttle_applies():
    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {"groq": {"requests_per_minute": 1}},
            "budgets": {},
        }
        # Fill the throttle window to exceed limit
        _throttle._windows["groq"] = _throttle._windows.get("groq", [])
        for _ in range(5):
            _throttle._windows["groq"].append(0)

        with pytest.raises(ThrottleError):
            gen = route_stream("default", [{"role": "user", "content": "Hi"}])
            list(gen)
    _throttle.clear("groq")


def test_route_stream_budget_applies():
    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {},
            "budgets": {"groq": {"daily_limit_usd": 5.0}},
        }
        with patch("rfd_model_router.router.get_adapter") as mock_get_adapter:
            with patch("rfd_model_router.router._get_daily_spend") as mock_spend:
                mock_spend.return_value = 10.0  # Exceeds budget of 5.0
                adapter = GroqAdapter()
                # Mock that accepts any kwargs including stream_options
                def mock_create(**kwargs):
                    return MagicMock(__iter__=lambda self: iter([]))
                adapter.client.chat.completions.create = mock_create
                mock_get_adapter.return_value = adapter

                with pytest.raises(BudgetExceededError):
                    gen = route_stream("default", [{"role": "user", "content": "Hi"}])
                    # Try to consume - should fail before yielding
                    for _ in gen:
                        pass


def test_sse_endpoint_returns_streaming_response():
    from fastapi.testclient import TestClient
    client = TestClient(app)

    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {},
            "budgets": {},
        }
        with patch("rfd_model_router.router.get_adapter") as mock_get_adapter:
            adapter = GroqAdapter()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Test"))]
            mock_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
            mock_response = MagicMock()
            mock_response.__iter__ = lambda self: iter([mock_chunk])
            adapter.client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_get_adapter.return_value = adapter

            response = client.post(
                "/route/stream",
                json={
                    "task_type": "default",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


def test_sse_format_correct():
    from fastapi.testclient import TestClient
    client = TestClient(app)

    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {},
            "budgets": {},
        }
        with patch("rfd_model_router.router.get_adapter") as mock_get_adapter:
            adapter = GroqAdapter()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Test"))]
            mock_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
            mock_response = MagicMock()
            mock_response.__iter__ = lambda self: iter([mock_chunk])
            adapter.client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_get_adapter.return_value = adapter

            response = client.post(
                "/route/stream",
                json={
                    "task_type": "default",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            content = response.text
            assert "data:" in content
            assert '"token":' in content
            assert '"done":' in content


def test_sse_final_event_has_metadata():
    from fastapi.testclient import TestClient
    client = TestClient(app)

    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {},
            "budgets": {},
        }
        with patch("rfd_model_router.router.get_adapter") as mock_get_adapter:
            adapter = GroqAdapter()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Test"))]
            mock_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
            mock_response = MagicMock()
            mock_response.__iter__ = lambda self: iter([mock_chunk])
            adapter.client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_get_adapter.return_value = adapter

            response = client.post(
                "/route/stream",
                json={
                    "task_type": "default",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data:")]
            final_event = json.loads(events[-1].replace("data: ", ""))
            assert final_event["done"] is True
            assert "provider" in final_event
            assert "model" in final_event
            assert "input_tokens" in final_event
            assert "output_tokens" in final_event
            assert "cost_usd" in final_event


def test_sse_error_yields_error_event():
    from fastapi.testclient import TestClient
    client = TestClient(app)

    with patch("rfd_model_router.router.load_config") as mock_config:
        mock_config.return_value = {
            "default": {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "pricing": {"input_per_million": 0.59, "output_per_million": 0.79},
                "max_context_tokens": 128000,
            },
            "rate_limits": {},
            "budgets": {},
        }
        with patch("rfd_model_router.router.get_adapter") as mock_get_adapter:
            adapter = GroqAdapter()
            adapter.client.chat.completions.create = MagicMock(side_effect=Exception("API error"))
            mock_get_adapter.return_value = adapter

            response = client.post(
                "/route/stream",
                json={
                    "task_type": "default",
                    "messages": [{"role": "user", "content": "Hi"}],
                },
            )
            content = response.text
            events = [line for line in content.split("\n") if line.startswith("data:")]
            final_event = json.loads(events[-1].replace("data: ", ""))
            assert final_event["done"] is True
            assert "error" in final_event
