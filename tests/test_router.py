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
        result = router.route("directive", [{"role": "user", "content": "hi"}])
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
            router.route("directive", [{"role": "user", "content": "hi"}])
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
            router.route("directive", [{"role": "user", "content": "hi"}])
        assert adapter.complete.call_count == 3


def test_timeout_triggers_retry():
    adapter = _mock_adapter()
    adapter.complete.side_effect = [TimeoutError("slow"), ("ok", 1, 2)]
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router.time.sleep"
    ):
        result = router.route("directive", [{"role": "user", "content": "hi"}])
        assert result[0] == "ok"
        assert adapter.complete.call_count == 2


def test_timeout_exhausted_raises():
    adapter = _mock_adapter()
    adapter.complete.side_effect = TimeoutError("slow")
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router.time.sleep"
    ):
        with pytest.raises(TimeoutError):
            router.route("directive", [{"role": "user", "content": "hi"}])
        assert adapter.complete.call_count == 3


def test_fallback_used_on_primary_failure():
    primary = _mock_adapter()
    primary.complete.side_effect = Exception("primary failed")
    fallback = _mock_adapter()
    fallback.complete.return_value = ("fallback", 2, 3)

    def side_effect(provider):
        if provider == "groq":
            return primary
        if provider == "anthropic":
            return fallback
        raise ValueError(provider)

    with patch("rfd_model_router.router.get_adapter", side_effect=side_effect), patch(
        "rfd_model_router.router.time.sleep"
    ):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result == ("fallback", "anthropic", "claude-haiku-4-5-20251001", 2, 3)


def test_fallback_success_returns_completion():
    primary = _mock_adapter()
    primary.complete.side_effect = Exception("primary failed")
    fallback = _mock_adapter()
    fallback.complete.return_value = ("ok", 5, 6)

    def side_effect(provider):
        if provider == "groq":
            return primary
        if provider == "anthropic":
            return fallback
        raise ValueError(provider)

    with patch("rfd_model_router.router.get_adapter", side_effect=side_effect), patch(
        "rfd_model_router.router.time.sleep"
    ):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result[0] == "ok"


def test_fallback_failure_raises():
    primary = _mock_adapter()
    primary.complete.side_effect = Exception("primary failed")
    fallback = _mock_adapter()
    fallback.complete.side_effect = Exception("fallback failed")

    def side_effect(provider):
        if provider == "groq":
            return primary
        if provider == "anthropic":
            return fallback
        raise ValueError(provider)

    with patch("rfd_model_router.router.get_adapter", side_effect=side_effect), patch(
        "rfd_model_router.router.time.sleep"
    ):
        with pytest.raises(Exception):
            router.route("code_transformation", [{"role": "user", "content": "hi"}])


def test_no_fallback_raises_immediately():
    adapter = _mock_adapter()
    adapter.complete.side_effect = TimeoutError("failed")
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router.time.sleep"
    ):
        with pytest.raises(TimeoutError):
            router.route("directive", [{"role": "user", "content": "hi"}])
        assert adapter.complete.call_count == 3


def test_fallback_not_retried_recursively():
    primary = _mock_adapter()
    primary.complete.side_effect = TimeoutError("primary failed")
    fallback = _mock_adapter()
    fallback.complete.side_effect = TimeoutError("fallback failed")

    def side_effect(provider):
        if provider == "groq":
            return primary
        if provider == "anthropic":
            return fallback
        raise ValueError(provider)

    with patch("rfd_model_router.router.get_adapter", side_effect=side_effect), patch(
        "rfd_model_router.router.time.sleep"
    ):
        with pytest.raises(TimeoutError):
            router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert primary.complete.call_count == 3
        assert fallback.complete.call_count == 3


def test_budget_under_limit_routes():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router._get_daily_spend", return_value=0.5
    ):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result[0] == "ok"


def test_budget_exceeded_falls_back():
    primary = _mock_adapter()
    primary.complete.side_effect = Exception("primary failed")
    fallback = _mock_adapter()
    fallback.complete.return_value = ("fallback", 2, 3)

    def side_effect(provider):
        if provider == "groq":
            return primary
        if provider == "anthropic":
            return fallback
        raise ValueError(provider)

    with patch("rfd_model_router.router.get_adapter", side_effect=side_effect), patch(
        "rfd_model_router.router._get_daily_spend", return_value=10.0
    ), patch("rfd_model_router.router._throttle.is_allowed", return_value=True):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result == ("fallback", "anthropic", "claude-haiku-4-5-20251001", 2, 3)


def test_budget_exceeded_no_fallback_raises():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router._get_daily_spend", return_value=10.0
    ), patch("rfd_model_router.router._throttle.is_allowed", return_value=True):
        with pytest.raises(router.BudgetExceededError):
            router.route("directive", [{"role": "user", "content": "hi"}])


def test_budget_zero_limit_never_blocks():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router._get_daily_spend", return_value=100.0
    ), patch("rfd_model_router.router._throttle.is_allowed", return_value=True):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result[0] == "ok"


def test_oversized_request_raises():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router._throttle.is_allowed", return_value=True
    ):
        large_msg = [{"role": "user", "content": "x" * 500000}]
        with pytest.raises(ValueError):
            router.route("code_transformation", large_msg)


def test_undersized_request_passes():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router._throttle.is_allowed", return_value=True
    ):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result[0] == "ok"


def test_throttle_falls_back_when_throttled():
    primary = _mock_adapter()
    primary.complete.return_value = ("ok", 1, 2)
    fallback = _mock_adapter()
    fallback.complete.return_value = ("fallback", 2, 3)

    def side_effect(provider):
        if provider == "groq":
            return primary
        if provider == "anthropic":
            return fallback
        raise ValueError(provider)

    def throttle_side_effect(provider, rpm):
        if provider == "groq":
            return False
        if provider == "anthropic":
            return True
        return True

    with patch("rfd_model_router.router.get_adapter", side_effect=side_effect), patch(
        "rfd_model_router.router._throttle.is_allowed", side_effect=throttle_side_effect
    ):
        result = router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert result == ("fallback", "anthropic", "claude-haiku-4-5-20251001", 2, 3)


def test_throttle_raises_no_fallback():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 1, 2)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router._throttle.is_allowed", return_value=False
    ):
        with pytest.raises(router.ThrottleError):
            router.route("directive", [{"role": "user", "content": "hi"}])


def test_cost_logged_in_db():
    adapter = _mock_adapter()
    adapter.complete.return_value = ("ok", 1000, 500)
    with patch("rfd_model_router.router.get_adapter", return_value=adapter), patch(
        "rfd_model_router.router._throttle.is_allowed", return_value=True
    ), patch("rfd_model_router.router.log_request") as mock_log:
        router.route("code_transformation", [{"role": "user", "content": "hi"}])
        assert mock_log.called
        call_kwargs = mock_log.call_args.kwargs
        assert "cost_usd" in call_kwargs
        assert call_kwargs["cost_usd"] > 0
