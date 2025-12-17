"""Additional tests for `ServiceClientAdapter` covering generated-client fallbacks."""

from __future__ import annotations

import sys
import types
from http import HTTPStatus
from importlib import import_module

import pytest

from adapter.service_client_adapter import (
    ServiceClientAdapter,
    _call_generated,
    _instantiate_generated_client,
)
from generated_client.mail_client_service_client.models.action_result import ActionResult
from generated_client.mail_client_service_client.models.message_detail import MessageDetail
from generated_client.mail_client_service_client.models.message_summary import MessageSummary

API_DEFAULT = import_module("generated_client.mail_client_service_client.api.default")


@pytest.mark.unit
def test_generated_client_code_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the adapter uses generated-client helpers when no `messages` API is present."""
    sentinel_client = object()
    monkeypatch.setattr(
        "adapter.service_client_adapter._instantiate_generated_client",
        lambda *_, **__: sentinel_client,
    )

    adapter = ServiceClientAdapter(base_url="http://example.com")

    max_results = 5

    def fake_list_sync(*, _client: object, _limit: int) -> list[MessageSummary]:
        assert _client is sentinel_client
        assert _limit == max_results
        return [MessageSummary(id="m42", subject="subject")]

    def fake_get_sync(*, _client: object, message_id: str) -> MessageDetail:
        assert _client is sentinel_client
        return MessageDetail(
            id=message_id,
            from_="sender@example.com",
            to="me@example.com",
            date="2025-01-01T00:00:00Z",
            subject="Hello",
            body="Body text",
        )

    def fake_delete_sync(*, client: object, message_id: str) -> ActionResult:
        assert client is sentinel_client
        return ActionResult(ok=True, message=f"deleted-{message_id}")

    def fake_mark_sync(*, _client: object, message_id: str) -> ActionResult:
        assert _client is sentinel_client
        return ActionResult(ok=True, message=f"marked-{message_id}")

    monkeypatch.setattr(API_DEFAULT.list_messages_messages_get, "sync", fake_list_sync)
    monkeypatch.setattr(API_DEFAULT.get_message_detail_messages_message_id_get, "sync", fake_get_sync)
    monkeypatch.setattr(API_DEFAULT.delete_message_messages_message_id_delete, "sync", fake_delete_sync)
    monkeypatch.setattr(
        API_DEFAULT.mark_message_as_read_messages_message_id_mark_as_read_post,
        "sync",
        fake_mark_sync,
    )

    messages = list(adapter.get_messages(max_results=max_results))
    assert messages[0].id == "m42"
    detail = adapter.get_message("m42")
    assert detail.subject == "Hello"
    assert adapter.delete_message("m42") is True
    assert adapter.mark_as_read("m42") is True


@pytest.mark.unit
def test_initializes_test_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the adapter sets up a FastAPI `TestClient` when targeting testserver."""
    captured = {}

    class DummyTestClient:
        """Record requests made by the adapter when using FastAPI TestClient."""

        def __init__(self, app: object) -> None:
            captured["app"] = app
            captured["requests"] = []

        def get(self, path: str, params: dict | None = None) -> object:
            """Record GET invocations and return canned responses."""
            captured["requests"].append(("GET", path, params))
            if path == "/messages":
                return types.SimpleNamespace(
                    status_code=HTTPStatus.OK,
                    json=lambda: [{"id": "m1", "subject": "Hello"}],
                    raise_for_status=lambda: None,
                )
            return types.SimpleNamespace(
                status_code=HTTPStatus.OK,
                json=lambda: {
                    "id": "m1",
                    "from_": "a@example.com",
                    "to": "b@example.com",
                    "date": "2025-01-01T00:00:00Z",
                    "subject": "Hello",
                    "body": "body",
                },
                raise_for_status=lambda: None,
            )

        def delete(self, path: str) -> object:
            """Record DELETE invocations and return canned responses."""
            captured["requests"].append(("DELETE", path, None))
            return types.SimpleNamespace(status_code=HTTPStatus.OK, json=lambda: {"ok": True})

        def post(self, path: str) -> object:
            """Record POST invocations and return canned responses."""
            captured["requests"].append(("POST", path, None))
            return types.SimpleNamespace(status_code=HTTPStatus.OK, json=lambda: {"ok": True})

    dummy_mail_service = types.SimpleNamespace(app=object())
    monkeypatch.setitem(sys.modules, "mail_client_service", dummy_mail_service)
    monkeypatch.setattr("fastapi.testclient.TestClient", DummyTestClient)

    adapter = ServiceClientAdapter(base_url="http://testserver")
    msgs = list(adapter.get_messages())
    assert msgs[0].subject == "Hello"
    detail = adapter.get_message("m1")
    assert detail.body == "body"
    assert adapter.delete_message("m1") is True
    assert adapter.mark_as_read("m1") is True
    assert captured["app"] is not None
    assert captured["requests"] == [
        ("GET", "/messages", {"limit": 10}),
        ("GET", "/messages/m1", None),
        ("DELETE", "/messages/m1", None),
        ("POST", "/messages/m1/mark-as-read", None),
    ]


@pytest.mark.unit
def test_messages_api_typeerror_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure we retry generated client helpers using alias mappings."""

    class FlakyMessages:
        """Simulate generated client endpoints with multiple calling conventions."""

        def __init__(self) -> None:
            self._list_calls = 0
            self.list_messages = types.SimpleNamespace(sync=self._list_sync)
            self.get_message = types.SimpleNamespace(sync=self._get_sync)
            self.delete_message = types.SimpleNamespace(sync=self._delete_sync)
            self.mark_as_read = types.SimpleNamespace(sync=self._mark_sync)

        def _list_sync(self, *args: object, **_kwargs: object) -> object:
            self._list_calls += 1
            if args:
                error_message = "positional not supported"
                raise TypeError(error_message)
            return types.SimpleNamespace(messages=[MessageSummary(id="m99", subject="retry")])

        def _get_sync(self, *_args: object, **kwargs: object) -> MessageDetail:
            if not kwargs:
                raise TypeError
            return MessageDetail(
                id=kwargs["message_id"],
                from_="bot@example.com",
                to="user@example.com",
                date="2025-01-01T00:00:00Z",
                subject="Retry Detail",
                body="Body",
            )

        def _delete_sync(self, *_args: object, **kwargs: object) -> ActionResult:
            if not kwargs:
                raise TypeError
            return ActionResult(ok=False, message="failed")

        def _mark_sync(self, *_args: object, **kwargs: object) -> ActionResult:
            if not kwargs:
                raise TypeError
            return ActionResult(ok=True, message="marked")

    fake_holder = types.SimpleNamespace(messages=FlakyMessages())
    monkeypatch.setattr(
        "adapter.service_client_adapter._instantiate_generated_client",
        lambda *_, **__: fake_holder,
    )

    adapter = ServiceClientAdapter(base_url="http://example.com")

    msgs = list(adapter.get_messages(max_results=2))
    assert msgs[0].id == "m99"
    detail = adapter.get_message("foo")
    assert detail.subject == "Retry Detail"
    assert adapter.delete_message("foo") is False
    assert adapter.mark_as_read("foo") is True


@pytest.mark.unit
def test_call_generated_aliases_and_failures() -> None:
    """Ensure `_call_generated` handles alias expansion and passthrough errors."""

    def accepts_aliases(*, _client: str, _limit: int, _message_id: str) -> tuple[str, int, str]:
        return _client, _limit, _message_id

    assert _call_generated(accepts_aliases, client="c", limit=3, message_id="m") == ("c", 3, "m")

    def always_type_error(**_: object) -> None:
        raise TypeError

    with pytest.raises(TypeError):
        _call_generated(always_type_error, client="c")


@pytest.mark.unit
def test_instantiate_generated_client_attempts() -> None:
    """Verify `_instantiate_generated_client` tries multiple constructor signatures."""
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    min_attempts = 4

    def factory(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append((args, kwargs))
        if len(calls) < min_attempts:
            raise TypeError
        return {"args": args, "kwargs": kwargs}

    result = _instantiate_generated_client(factory, "http://example.com")
    assert result["kwargs"] == {}

    def factory_fail(*args: object, **kwargs: object) -> None:
        raise TypeError

    with pytest.raises(TypeError):
        _instantiate_generated_client(factory_fail, "http://x")
