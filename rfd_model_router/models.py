import uuid
import time as _time
from pydantic import BaseModel, field_validator


class Message(BaseModel):
    role: str
    content: str


class RouteRequest(BaseModel):
    task_type: str
    messages: list[Message]
    system_prompt: str | None = None

    @field_validator("messages")
    @classmethod
    def messages_not_empty(cls, v):
        if not v:
            raise ValueError("messages must not be empty")
        return v


class RouteResponse(BaseModel):
    completion: str
    provider: str
    model: str
    tokens: dict


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIRequest(BaseModel):
    model: str = "cline"
    messages: list[OpenAIMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    # All other OpenAI fields silently ignored


class OpenAIUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIChoice(BaseModel):
    index: int = 0
    message: dict  # {"role": "assistant", "content": "..."}
    finish_reason: str = "stop"


class OpenAIResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[OpenAIChoice]
    usage: OpenAIUsage
