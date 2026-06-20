import time

from rfd_model_router.throttle import _throttle


def test_throttle_allows_under_limit():
    _throttle.clear("test_provider")
    for _ in range(5):
        assert _throttle.is_allowed("test_provider", 10)


def test_throttle_blocks_at_limit():
    _throttle.clear("test_provider")
    for _ in range(10):
        assert _throttle.is_allowed("test_provider", 10)
    assert not _throttle.is_allowed("test_provider", 10)


def test_throttle_clears_after_window():
    _throttle.clear("test_provider")
    for _ in range(10):
        _throttle.is_allowed("test_provider", 10)
    assert not _throttle.is_allowed("test_provider", 10)
    _throttle.clear("test_provider")
    assert _throttle.is_allowed("test_provider", 10)


def test_throttle_zero_rpm_always_allows():
    _throttle.clear("test_provider")
    for _ in range(100):
        assert _throttle.is_allowed("test_provider", 0)
