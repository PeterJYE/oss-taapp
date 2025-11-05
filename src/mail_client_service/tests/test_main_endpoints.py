import pytest


@pytest.mark.integration
def test_list_and_detail_endpoints(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from mail_client_service import app

    class DummyMsg:
        def __init__(self, id, subject=None):
            self.id = id
            self.subject = subject
            self.from_ = "a@b.com"
            self.to = "me@me.com"
            self.date = "2025-01-01T00:00:00Z"
            self.body = "hi"

    class DummyClient:
        def __init__(self):
            self._msgs = [DummyMsg("m1", "s1"), DummyMsg("m2")]

        def get_messages(self, max_results: int = 10):
            for m in self._msgs[:max_results]:
                yield m

        def get_message(self, message_id: str):
            for m in self._msgs:
                if m.id == message_id:
                    return m
            raise KeyError("not found")

        def delete_message(self, message_id: str) -> bool:
            for i, m in enumerate(self._msgs):
                if m.id == message_id:
                    del self._msgs[i]
                    return True
            return False

        def mark_as_read(self, message_id: str) -> bool:
            return any(m.id == message_id for m in self._msgs)

    dummy = DummyClient()
    # Override dependency
    from mail_client_service.main import get_client_dep
    app.dependency_overrides[get_client_dep] = lambda: dummy

    client = TestClient(app, raise_server_exceptions=False)

    # list messages happy path
    r = client.get("/messages?limit=2")
    assert r.status_code == 200
    js = r.json()
    assert isinstance(js, list)
    assert js[0]["id"] == "m1"

    # detail happy path
    r2 = client.get("/messages/m1")
    assert r2.status_code == 200
    d = r2.json()
    assert d["id"] == "m1"

    # mark as read happy
    r3 = client.post("/messages/m1/mark-as-read")
    assert r3.status_code == 200

    # delete happy
    r4 = client.delete("/messages/m1")
    assert r4.status_code == 200


@pytest.mark.integration
def test_endpoints_error_paths(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from mail_client_service import app

    # Dependency that raises to test 500/404 handling
    def bad_dep():
        raise RuntimeError("boom")

    from mail_client_service.main import get_client_dep
    app.dependency_overrides[get_client_dep] = bad_dep

    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/messages")
    assert r.status_code == 500

    r2 = client.get("/messages/doesnotexist")
    # since dependency raises, endpoint should return 404-like wrapper
    assert r2.status_code in (404, 500)
