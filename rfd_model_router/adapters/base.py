from abc import ABC, abstractmethod
from collections.abc import Generator


class BaseAdapter(ABC):
    @abstractmethod
    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> tuple[str, int, int]:
        ...

    @abstractmethod
    def stream(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
        timeout: int = 30,
    ) -> Generator[str, None, tuple[int, int]]:
        """
        Yields text chunks as they arrive.
        When exhausted, the generator's return value is (input_tokens, output_tokens).
        Caller retrieves via: tokens = gen.send(None) after StopIteration.
        Token counts may be 0 if provider does not expose them during streaming.
        """
        ...
