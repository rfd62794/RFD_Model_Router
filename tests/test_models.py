import pytest
from pydantic import ValidationError

from rfd_model_router.models import Message, RouteRequest


def test_valid_request_passes_validation():
    req = RouteRequest(
        task_type="code_transformation",
        messages=[Message(role="user", content="hello")],
        system_prompt="sys",
    )
    assert req.task_type == "code_transformation"
    assert req.messages[0].role == "user"
    assert req.messages[0].content == "hello"
    assert req.system_prompt == "sys"


def test_empty_messages_fails_validation():
    with pytest.raises(ValidationError):
        RouteRequest(task_type="code_transformation", messages=[])


def test_missing_role_fails_validation():
    with pytest.raises(ValidationError):
        RouteRequest(task_type="code_transformation", messages=[{"content": "hi"}])


def test_missing_content_fails_validation():
    with pytest.raises(ValidationError):
        RouteRequest(task_type="code_transformation", messages=[{"role": "user"}])
