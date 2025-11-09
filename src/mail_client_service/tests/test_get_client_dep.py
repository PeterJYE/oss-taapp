"""Tests for mail client service dependency injection."""

from __future__ import annotations

import pytest

from mail_client_service.main import get_client_dep


def _require_mail_client_api() -> object:
    """Import the optional `mail_client_api` package or skip tests."""
    return pytest.importorskip("mail_client_api")


@pytest.mark.unit
def test_get_client_dep_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_client_dep` should return a client instance when available."""
    mail_client_module = _require_mail_client_api()
    monkeypatch.setattr(mail_client_module, "get_client", lambda _interactive=True: object())

    client = get_client_dep()
    assert client is not None


@pytest.mark.unit
def test_get_client_dep_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_client_dep` should propagate errors from the API client factory."""
    mail_client_module = _require_mail_client_api()
    runtime_error = RuntimeError("oops")

    def _raise_client(*_args: object, **_kwargs: object) -> object:
        raise runtime_error

    monkeypatch.setattr(mail_client_module, "get_client", _raise_client)

    with pytest.raises(RuntimeError, match="oops"):
        get_client_dep()
