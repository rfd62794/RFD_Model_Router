from unittest.mock import MagicMock

import pytest

from rfd_model_router.adapters.openrouter_adapter import (
    OpenRouterAdapter,
    OPENROUTER_BASE_URL,
    ATTRIBUTION_HEADERS,
)
from rfd_model_router.router import _is_retriable


def test_openrouter_has_attribution_headers():
    adapter = OpenRouterAdapter()
    client_headers = adapter.client.default_headers
    assert "HTTP-Referer" in client_headers
    assert client_headers["HTTP-Referer"] == "https://rfditservices.com"
    assert "X-Title" in client_headers
    assert client_headers["X-Title"] == "RFD Model Router"


def test_openrouter_complete_returns_tokens():
    adapter = OpenRouterAdapter()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
    mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
    adapter.client.chat.completions.create = MagicMock(return_value=mock_response)

    text, input_tokens, output_tokens = adapter.complete(
        "anthropic/claude-3.5-sonnet", [{"role": "user", "content": "Hi"}]
    )
    assert text == "Test response"
    assert input_tokens == 10
    assert output_tokens == 5


def test_openrouter_stream_includes_usage_option():
    adapter = OpenRouterAdapter()
    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock(delta=MagicMock(content="Test"))]
    mock_chunk.choices[0].finish_reason = "stop"
    mock_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
    mock_response = MagicMock()
    mock_response.__iter__ = lambda self: iter([mock_chunk])
    adapter.client.chat.completions.create = MagicMock(return_value=mock_response)

    gen = adapter.stream("anthropic/claude-3.5-sonnet", [{"role": "user", "content": "Hi"}])
    list(gen)

    adapter.client.chat.completions.create.assert_called_once()
    call_kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert "stream_options" in call_kwargs
    assert call_kwargs["stream_options"] == {"include_usage": True}


def test_openrouter_stream_stops_on_error_finish_reason():
    adapter = OpenRouterAdapter()
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
    mock_chunk1.choices[0].finish_reason = None
    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [MagicMock(delta=MagicMock(content=""))]
    mock_chunk2.choices[0].finish_reason = "error"
    mock_response = MagicMock()
    mock_response.__iter__ = lambda self: iter([mock_chunk1, mock_chunk2])
    adapter.client.chat.completions.create = MagicMock(return_value=mock_response)

    gen = adapter.stream("anthropic/claude-3.5-sonnet", [{"role": "user", "content": "Hi"}])
    chunks = list(gen)
    assert chunks == ["Hello"]  # Should stop after error, not yield empty chunk


def test_is_retriable_excludes_402():
    mock_error = MagicMock()
    mock_error.status_code = 402
    assert _is_retriable(mock_error) is False

    # Verify other retriable codes still work
    mock_error.status_code = 429
    assert _is_retriable(mock_error) is True
    mock_error.status_code = 503
    assert _is_retriable(mock_error) is True
