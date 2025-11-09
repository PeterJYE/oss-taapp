"""Unit tests for the Pydantic models in `mail_client_service.models`."""

from mail_client_service.src import models


def test_message_summary_aliases() -> None:
    """Serialising summaries should respect alias fields."""
    summary = models.MessageSummary(
        id="msg-1",
        from_="alice@example.com",
        to="bob@example.com",
        date="2025-01-01T00:00:00Z",
        subject="Hello",
    )
    dumped = summary.model_dump(by_alias=True)
    assert dumped["from"] == "alice@example.com"
    assert dumped["to"] == "bob@example.com"


def test_message_detail_roundtrip() -> None:
    """MessageDetail roundtrips via model_dump/model_validate."""
    detail = models.MessageDetail(
        id="msg-2",
        from_="carol@example.com",
        to="dave@example.com",
        date="2025-01-02T00:00:00Z",
        subject="Greetings",
        body="Body text",
    )
    serialized = detail.model_dump(by_alias=True)
    restored = models.MessageDetail.model_validate(serialized)
    assert restored.body == "Body text"


def test_message_list_response_and_success_response() -> None:
    """Composite responses expose expected fields."""
    summary = models.MessageSummary(
        id="msg-3",
        from_="eve@example.com",
        to="frank@example.com",
        date="2025-01-03T00:00:00Z",
        subject="Subject",
    )
    response = models.MessageListResponse(messages=[summary], count=1)
    assert response.count == 1
    assert response.messages[0].id == "msg-3"

    success = models.SuccessResponse(success=True, message="ok")
    assert success.success is True
    assert success.message == "ok"


def test_error_response_optional_detail() -> None:
    """Optional detail should remain None."""
    err = models.ErrorResponse(error="Failure", detail=None)
    assert err.detail is None

