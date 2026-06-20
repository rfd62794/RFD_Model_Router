from collections import deque
from threading import Lock
import time

WINDOW_SECONDS = 60


class SlidingWindowThrottle:
    """Thread-safe per-provider sliding window rate limiter."""

    def __init__(self):
        self._windows: dict[str, deque] = {}
        self._lock = Lock()

    def is_allowed(self, provider: str, requests_per_minute: int) -> bool:
        """
        Returns True if the request is within the rate limit.
        Returns True if requests_per_minute is 0 (no limit).
        Side effect: records the request timestamp if allowed.
        """
        if requests_per_minute == 0:
            return True

        with self._lock:
            now = time.time()
            window = self._windows.get(provider)
            if window is None:
                window = deque()
                self._windows[provider] = window

            # Remove timestamps older than the window
            while window and now - window[0] >= WINDOW_SECONDS:
                window.popleft()

            # Check if under limit
            if len(window) < requests_per_minute:
                window.append(now)
                return True
            return False

    def clear(self, provider: str) -> None:
        """Reset the window for a provider. Used in tests."""
        with self._lock:
            self._windows.pop(provider, None)


_throttle = SlidingWindowThrottle()
