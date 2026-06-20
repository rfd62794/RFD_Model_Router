from unittest.mock import MagicMock, patch

from rfd_model_router.adapters.anthropic_adapter import AnthropicAdapter
from rfd_model_router.adapters.base import BaseAdapter
from rfd_model_router.adapters.gemini_adapter import GeminiAdapter
from rfd_model_router.adapters.groq_adapter import GroqAdapter
from rfd_model_router.adapters.openrouter_adapter import OpenRouterAdapter


def test_all_adapters_implement_base():
    for cls in [AnthropicAdapter, GroqAdapter, GeminiAdapter, OpenRouterAdapter]:
        assert issubclass(cls, BaseAdapter)
        assert hasattr(cls, "complete")


def test_anthropic_adapter_returns_tuple():
    with patch("rfd_model_router.adapters.anthropic_adapter.Anthropic") as MockClient:
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text="hello")]
        response.usage.input_tokens = 10
        response.usage.output_tokens = 5
        client.messages.create.return_value = response
        MockClient.return_value = client

        adapter = AnthropicAdapter()
        result = adapter.complete("claude-haiku", [{"role": "user", "content": "hi"}], "sys")
        assert result == ("hello", 10, 5)


def test_anthropic_system_prompt_not_prepended():
    with patch("rfd_model_router.adapters.anthropic_adapter.Anthropic") as MockClient:
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text="hello")]
        response.usage.input_tokens = 1
        response.usage.output_tokens = 1
        client.messages.create.return_value = response
        MockClient.return_value = client

        adapter = AnthropicAdapter()
        adapter.complete("claude-haiku", [{"role": "user", "content": "hi"}], "sys")
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["system"] == "sys"
        assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


def test_groq_adapter_returns_tuple():
    with patch("rfd_model_router.adapters.groq_adapter.Groq") as MockClient:
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="hello"))]
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 5
        client.chat.completions.create.return_value = response
        MockClient.return_value = client

        adapter = GroqAdapter()
        result = adapter.complete("llama", [{"role": "user", "content": "hi"}], "sys")
        assert result == ("hello", 10, 5)


def test_groq_system_prompt_prepended():
    with patch("rfd_model_router.adapters.groq_adapter.Groq") as MockClient:
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="hello"))]
        response.usage.prompt_tokens = 1
        response.usage.completion_tokens = 1
        client.chat.completions.create.return_value = response
        MockClient.return_value = client

        adapter = GroqAdapter()
        adapter.complete("llama", [{"role": "user", "content": "hi"}], "sys")
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["messages"][0] == {"role": "system", "content": "sys"}
        assert kwargs["messages"][1] == {"role": "user", "content": "hi"}


def test_gemini_adapter_returns_tuple():
    with patch("rfd_model_router.adapters.gemini_adapter.genai") as MockGenai:
        client = MagicMock()
        response = MagicMock()
        response.text = "hello"
        response.usage_metadata.prompt_token_count = 10
        response.usage_metadata.candidates_token_count = 5
        client.models.generate_content.return_value = response
        MockGenai.Client.return_value = client

        adapter = GeminiAdapter()
        result = adapter.complete("gemini", [{"role": "user", "content": "hi"}], "sys")
        assert result == ("hello", 10, 5)


def test_gemini_adapter_uses_new_sdk():
    with patch("rfd_model_router.adapters.gemini_adapter.genai") as MockGenai:
        client = MagicMock()
        response = MagicMock()
        response.text = "ok"
        response.usage_metadata.prompt_token_count = 4
        response.usage_metadata.candidates_token_count = 2
        client.models.generate_content.return_value = response
        MockGenai.Client.return_value = client

        adapter = GeminiAdapter()
        adapter.complete("gemini-2.0-flash-exp", [{"role": "user", "content": "hi"}])
        MockGenai.Client.assert_called_once()
        client.models.generate_content.assert_called_once()


def test_openrouter_adapter_returns_tuple():
    with patch("rfd_model_router.adapters.openrouter_adapter.OpenAI") as MockClient:
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="hello"))]
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 5
        client.chat.completions.create.return_value = response
        MockClient.return_value = client

        adapter = OpenRouterAdapter()
        result = adapter.complete("model", [{"role": "user", "content": "hi"}], "sys")
        assert result == ("hello", 10, 5)
