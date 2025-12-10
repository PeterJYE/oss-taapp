import pytest


@pytest.mark.unit
def test_generated_client_client_and_api_asgi():
    """Construct the generated Client with an in-process FastAPI app and call
    several API functions to exercise request/response parsing without network.
    """
    pytest.importorskip("fastapi")
    pytest.importorskip("generated_client.mail_client_service_client.client")

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.get("/messages")
    def list_messages(limit: int = 10):
        return JSONResponse([{"id": "m1", "subject": "s1"}, {"id": "m2", "subject": "s2"}])

    @app.get("/messages/{message_id}")
    def get_message(message_id: str):
        return JSONResponse(
            {
                "id": message_id,
                "from_": "alice@example.com",
                "to": "me@example.com",
                "date": "2025-01-01T00:00:00Z",
                "subject": "hi",
                "body": "hello",
            }
        )

    @app.delete("/messages/{message_id}")
    def delete_message(message_id: str):
        return JSONResponse({"ok": True, "message": "deleted"})

    @app.post("/messages/{message_id}/mark-as-read")
    def mark_as_read(message_id: str):
        return JSONResponse({"ok": True, "message": "marked"})

    import urllib.parse

    from fastapi.testclient import TestClient as FastAPITestClient

    from generated_client.mail_client_service_client.api.default import (
        delete_message_messages_message_id_delete as delete_mod,
    )
    from generated_client.mail_client_service_client.api.default import (
        get_message_detail_messages_message_id_get as get_mod,
    )
    from generated_client.mail_client_service_client.api.default import (
        list_messages_messages_get as list_mod,
    )
    from generated_client.mail_client_service_client.api.default import (
        mark_message_as_read_messages_message_id_mark_as_read_post as mark_mod,
    )
    from generated_client.mail_client_service_client.client import Client

    tc = FastAPITestClient(app)

    class TestClientAdapter:
        def __init__(self, test_client, base_url: str = "http://testserver"):
            self._tc = test_client
            self._base = base_url

        def request(self, method: str, url: str, params=None, headers=None, json=None, data=None, timeout=None):
            parsed = urllib.parse.urlparse(url)
            path = parsed.path or "/"
            resp = self._tc.request(method, path, params=params, json=json, data=data, headers=headers)

            class RespProxy:
                def __init__(self, r):
                    self._r = r

                @property
                def status_code(self):
                    return self._r.status_code

                def json(self):
                    return self._r.json()

                @property
                def headers(self):
                    return self._r.headers

                @property
                def text(self):
                    return self._r.text

                @property
                def content(self):
                    return self._r.content

            return RespProxy(resp)

    client = Client(base_url="http://testserver")
    client.set_httpx_client(TestClientAdapter(tc, base_url="http://testserver"))

    msgs = list_mod.sync(client=client, limit=10)
    assert len(msgs) >= 1
    first = msgs[0]
    assert hasattr(first, "id") and hasattr(first, "subject")

    detail = get_mod.sync(client=client, message_id="m1")
    assert detail.id == "m1"

    res = delete_mod.sync(client=client, message_id="m1")
    assert getattr(res, "ok", True) is True

    res2 = mark_mod.sync(client=client, message_id="m1")
    assert getattr(res2, "ok", True) is True
