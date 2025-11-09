import pytest


@pytest.mark.unit
def test_message_models_roundtrip():
    pytest.importorskip("generated_client.mail_client_service_client.models.message_summary")
    pytest.importorskip("generated_client.mail_client_service_client.models.message_detail")

    from generated_client.mail_client_service_client.models.message_detail import MessageDetail
    from generated_client.mail_client_service_client.models.message_summary import MessageSummary

    s = MessageSummary(id="m1", subject="sub")
    d = MessageDetail(id="m1", from_="a@b.com", to="me@me.com", date="2025-01-01T00:00:00Z", subject="sub", body="b")

    sd = s.to_dict()
    dd = d.to_dict()

    assert sd["id"] == "m1"
    assert dd["body"] == "b"
