from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    @abstractmethod
    def complete(
        self,
        model: str,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> tuple[str, int, int]:
        ...
