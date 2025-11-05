import pytest


@pytest.mark.unit
def test_adapter_calls_generated_api_modules(monkeypatch):
    """Ensure ServiceClientAdapter uses the generated API module sync functions when present."""
    from types import SimpleNamespace

    from adapter.service_client_adapter import ServiceClientAdapter

    # Provide a fake generated_client.Client so adapter.__init__ succeeds
    class FakeClient:
        def __init__(self, base_url: str = "http://real"):
            self.base_url = base_url

    monkeypatch.setitem(__import__("sys").modules, "generated_client", SimpleNamespace(Client=FakeClient))

    # Monkeypatch the API module functions used by the adapter
    import importlib
    list_mod = importlib.import_module("generated_client.mail_client_service_client.api.default.list_messages_messages_get")
    get_mod = importlib.import_module("generated_client.mail_client_service_client.api.default.get_message_detail_messages_message_id_get")
    delete_mod = importlib.import_module("generated_client.mail_client_service_client.api.default.delete_message_messages_message_id_delete")
    mark_mod = importlib.import_module("generated_client.mail_client_service_client.api.default.mark_message_as_read_messages_message_id_mark_as_read_post")

    monkeypatch.setattr(list_mod, "sync", lambda client, limit: [SimpleNamespace(id="m1", subject="s1")])
    monkeypatch.setattr(get_mod, "sync", lambda client, message_id: SimpleNamespace(id=message_id, from_="a@b.com", to="me", date="d", subject="s", body="b"))
    monkeypatch.setattr(delete_mod, "sync", lambda client, message_id: SimpleNamespace(ok=True))
    monkeypatch.setattr(mark_mod, "sync", lambda client, message_id: SimpleNamespace(ok=True))

    adapter = ServiceClientAdapter(base_url="http://real")

    msgs = list(adapter.get_messages(max_results=10))
    assert len(msgs) == 1 and msgs[0].id == "m1"

    detail = adapter.get_message("m1")
    assert detail.id == "m1" and detail.from_ == "a@b.com"

    assert adapter.delete_message("m1") is True
    assert adapter.mark_as_read("m1") is True


@pytest.mark.unit
def test_adapter_returns_false_on_api_exceptions(monkeypatch):
    from types import SimpleNamespace

    from adapter.service_client_adapter import ServiceClientAdapter

    class FakeClient:
        def __init__(self, base_url: str = "http://real"):
            self.base_url = base_url

    monkeypatch.setitem(__import__("sys").modules, "generated_client", SimpleNamespace(Client=FakeClient))

    import importlib
    delete_mod = importlib.import_module("generated_client.mail_client_service_client.api.default.delete_message_messages_message_id_delete")
    mark_mod = importlib.import_module("generated_client.mail_client_service_client.api.default.mark_message_as_read_messages_message_id_mark_as_read_post")

    def raise_exc(client, message_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(delete_mod, "sync", raise_exc)
    monkeypatch.setattr(mark_mod, "sync", raise_exc)

    adapter = ServiceClientAdapter(base_url="http://real")

    assert adapter.delete_message("m1") is False
    assert adapter.mark_as_read("m1") is False
