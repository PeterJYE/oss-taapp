from types import SimpleNamespace

from generated_client.models import MessageSummary, MessageDetail, ActionResult


class FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.content = b"content"
        self.headers = {}

    def json(self):
        return self._payload


class FakeHTTPClient:
    def __init__(self, payload):
        self._payload = payload

    def request(self, **kwargs):
        return FakeResponse(200, self._payload)


class FakeClient:
    def __init__(self, payload):
        self._payload = payload

    def get_httpx_client(self):
        return FakeHTTPClient(self._payload)


def test_list_messages_api_module():
    from generated_client.mail_client_service_client.api.default import list_messages_messages_get as list_mod

    payload = [{"id": "m1", "subject": "s1"}, {"id": "m2", "subject": "s2"}]
    fake = FakeClient(payload)
    parsed = list_mod.sync(client=fake, limit=2)
    assert isinstance(parsed, list)
    assert isinstance(parsed[0], MessageSummary)
    assert parsed[0].id == "m1"


def test_get_message_detail_api_module():
    from generated_client.mail_client_service_client.api.default import get_message_detail_messages_message_id_get as get_mod

    payload = {"id": "m1", "from_": "a@b.com", "to": "me@me.com", "date": "2025-01-01T00:00:00Z", "subject": "s", "body": "b"}
    fake = FakeClient(payload)
    parsed = get_mod.sync(client=fake, message_id="m1")
    assert isinstance(parsed, MessageDetail)
    assert parsed.id == "m1"


def test_mark_read_and_delete_modules():
    from generated_client.mail_client_service_client.api.default import (
        mark_message_as_read_messages_message_id_mark_as_read_post as mark_mod,
        delete_message_messages_message_id_delete as del_mod,
    )

    payload = {"ok": True, "message": "done"}
    fake = FakeClient(payload)
    parsed_mark = mark_mod.sync(client=fake, message_id="m1")
    assert isinstance(parsed_mark, ActionResult)
    assert parsed_mark.ok is True

    parsed_del = del_mod.sync(client=fake, message_id="m1")
    assert isinstance(parsed_del, ActionResult)
    assert parsed_del.ok is True
