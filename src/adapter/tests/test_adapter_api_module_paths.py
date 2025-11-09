"""Tests for adapter API module path handling."""

import importlib
import sys
from types import SimpleNamespace
from typing import Never

import pytest

from adapter.service_client_adapter import ServiceClientAdapter


@pytest.mark.unit
def test_adapter_calls_generated_api_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ServiceClientAdapter uses the generated API module sync functions when present."""

    class FakeClient:
        """Fake generated client for testing."""

        def __init__(self, base_url: str = "http://real") -> None:
            """Initialize fake client with base URL."""
            self.base_url = base_url

    monkeypatch.setitem(sys.modules, "generated_client", SimpleNamespace(Client=FakeClient))

    list_mod = importlib.import_module(
        "generated_client.mail_client_service_client.api.default.list_messages_messages_get",
    )
    get_mod = importlib.import_module(
        "generated_client.mail_client_service_client.api.default.get_message_detail_messages_message_id_get",
    )
    delete_mod = importlib.import_module(
        "generated_client.mail_client_service_client.api.default.delete_message_messages_message_id_delete",
    )
    mark_mod = importlib.import_module(
        "generated_client.mail_client_service_client.api.default.mark_message_as_read_messages_message_id_mark_as_read_post",
    )

    monkeypatch.setattr(list_mod, "sync", lambda _client, _limit: [SimpleNamespace(id="m1", subject="s1")])
    monkeypatch.setattr(
        get_mod,
        "sync",
        lambda _client, message_id: SimpleNamespace(
            id=message_id,
            from_="a@b.com",
            to="me",
            date="d",
            subject="s",
            body="b",
        ),
    )
    monkeypatch.setattr(delete_mod, "sync", lambda _client, _message_id: SimpleNamespace(ok=True))
    monkeypatch.setattr(mark_mod, "sync", lambda _client, _message_id: SimpleNamespace(ok=True))

    adapter = ServiceClientAdapter(base_url="http://real")

    msgs = list(adapter.get_messages(max_results=10))
    assert len(msgs) == 1
    assert msgs[0].id == "m1"

    detail = adapter.get_message("m1")
    assert detail.id == "m1"
    assert detail.from_ == "a@b.com"

    assert adapter.delete_message("m1") is True
    assert adapter.mark_as_read("m1") is True


@pytest.mark.unit
def test_adapter_returns_false_on_api_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test adapter returns False when API calls raise exceptions."""

    class FakeClient:
        """Fake generated client for testing."""

        def __init__(self, base_url: str = "http://real") -> None:
            """Initialize fake client with base URL."""
            self.base_url = base_url

    monkeypatch.setitem(sys.modules, "generated_client", SimpleNamespace(Client=FakeClient))

    delete_mod = importlib.import_module(
        "generated_client.mail_client_service_client.api.default.delete_message_messages_message_id_delete",
    )
    mark_mod = importlib.import_module(
        "generated_client.mail_client_service_client.api.default.mark_message_as_read_messages_message_id_mark_as_read_post",
    )

    def raise_exc(_client: object, _message_id: str) -> Never:
        """Raise exception for testing error handling."""
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(delete_mod, "sync", raise_exc)
    monkeypatch.setattr(mark_mod, "sync", raise_exc)

    adapter = ServiceClientAdapter(base_url="http://real")

    assert adapter.delete_message("m1") is False
    assert adapter.mark_as_read("m1") is False
