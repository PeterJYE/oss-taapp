import pytest


@pytest.mark.unit
def test_get_client_dep_success(monkeypatch, tmp_path):
    pytest.importorskip("mail_client_api")
    from mail_client_service.main import get_client_dep

    # Monkeypatch mail_client_api.get_client to return a sentinel object
    import mail_client_api
    monkeypatch.setattr(mail_client_api, "get_client", lambda interactive=True: object())

    # Ensure function returns without raising
    client = get_client_dep()
    assert client is not None


@pytest.mark.unit
def test_get_client_dep_failure(monkeypatch):
    pytest.importorskip("mail_client_api")
    from mail_client_service.main import get_client_dep

    import mail_client_api
    monkeypatch.setattr(mail_client_api, "get_client", lambda interactive=True: (_ for _ in ()).throw(RuntimeError("oops")))

    with pytest.raises(Exception):
        _ = get_client_dep()
