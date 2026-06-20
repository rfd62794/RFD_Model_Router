import pytest

from rfd_model_router.pricer import calculate_cost, estimate_tokens


def test_calculate_cost_correct():
    pricing = {"input_per_million": 0.59, "output_per_million": 0.79}
    cost = calculate_cost(1_000_000, 1_000_000, pricing)
    assert cost == pytest.approx(1.38)


def test_calculate_cost_zero_tokens():
    pricing = {"input_per_million": 0.59, "output_per_million": 0.79}
    cost = calculate_cost(0, 0, pricing)
    assert cost == 0.0


def test_calculate_cost_missing_pricing():
    cost = calculate_cost(1000, 1000, None)
    assert cost == 0.0


def test_estimate_tokens_returns_int():
    messages = [{"role": "user", "content": "hello world"}]
    estimated = estimate_tokens(messages)
    assert isinstance(estimated, int)
    assert estimated > 0
