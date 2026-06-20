import asyncio

import pytest
from unittest.mock import MagicMock, patch

from rfd_model_router import router, server


def _mock_adapter():
    adapter = MagicMock()
    adapter.complete.return_value = ("ok", 1, 2)
    return adapter


def test_known_task_type_routes_correctly():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("code", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result[1] == "groq"
        assert result[2] == "llama-3.3-70b-versatile"


def test_unknown_task_type_falls_back():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("fallback", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter):
        result = router.route("unknown_task", [{"role": "user", "content": "hi"}])
        assert result[1] == "anthropic"
        assert result[2] == "claude-haiku-4-5-20251001"


def test_explicit_default_used_when_no_match():
    config = router.load_config()
    assert "default" in config
    assert config["default"]["provider"] == "anthropic"


def test_router_missing_config_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(router, "CONFIG_PATH", tmp_path / "nonexistent.yaml")
    with pytest.raises(Exception):
        router.load_config()


def test_get_adapter_unknown_provider_raises():
    with pytest.raises(ValueError):
        router.get_adapter("not_real")


def test_route_returns_provider_and_model():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("content", 3, 4)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter):
        result = router.route("content", [{"role": "user", "content": "hi"}])
        assert result == ("content", "gemini", "gemini-2.0-flash-exp", 3, 4)


def test_system_prompt_none_is_valid():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 0, 0)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}], None)
        assert result[0] == "ok"
        kwargs = adapter.complete.call_args.kwargs
        assert "system_prompt" in kwargs
        assert kwargs["system_prompt"] is None


def test_log_failure_does_not_fail_route():
    with patch("rfd_model_router.server.route") as mock_route, patch(
        "rfd_model_router.server.log_request"
    ) as mock_log:
        mock_route.return_value = ("ok", "anthropic", "claude", 1, 2)
        mock_log.side_effect = Exception("log failed")

        result = asyncio.run(
            server.route_completion("directive", [{"role": "user", "content": "hi"}])
        )
        assert result == "ok"


def test_retry_on_429():
    adapter = _mock_adapter()
    err = Exception("rate limited")
    err.status_code = 429
    adapter.complete.side_effect = [err, err, ("ok", 1, 2)]
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router.time.sleep"
    ):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result[0] == "ok"
        assert adapter.complete.call_count == 3


def test_no_retry_on_400():
    adapter = _mock_adapter()
    err = Exception("bad request")
    err.status_code = 400
    adapter.complete.side_effect = err
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router.time.sleep"
    ) as mock_sleep:
        with pytest.raises(Exception):
            router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert adapter.complete.call_count == 1
        mock_sleep.assert_not_called()


def test_max_retries_exceeded_raises():
    adapter = _mock_adapter()
    err = Exception("rate limited")
    err.status_code = 429
    adapter.complete.side_effect = [err, err, err]
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router.time.sleep"
    ):
        with pytest.raises(Exception):
            router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert adapter.complete.call_count == 3
