"""Tests for mail client service dependency injection."""

import pytest


@pytest.mark.unit
def test_get_client_dep_success(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """Test get_client_dep successfully retrieves client."""
    pytest.importorskip("mail_client_api")
    import mail_client_api  # noqa: PLC0415
    from mail_client_service.main import get_client_dep  # noqa: PLC0415

    monkeypatch.setattr(mail_client_api, "get_client", lambda _interactive=True: object())

    client = get_client_dep()
    assert client is not None


@pytest.mark.unit
def test_get_client_dep_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_client_dep raises exception when get_client fails."""
    pytest.importorskip("mail_client_api")
    import mail_client_api  # noqa: PLC0415
    from mail_client_service.main import get_client_dep  # noqa: PLC0415

    monkeypatch.setattr(
        mail_client_api,
        "get_client",
        lambda _interactive=True: (_ for _ in ()).throw(RuntimeError("oops")),
    )

    with pytest.raises(RuntimeError, match="oops"):
        _ = get_client_dep()
