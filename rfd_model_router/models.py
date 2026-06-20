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
