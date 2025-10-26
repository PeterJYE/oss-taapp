from generated_client.models import MessageSummary, MessageDetail


def test_message_summary_roundtrip():
    m = MessageSummary(id="m1", subject="Hello")
    d = m.to_dict()
    assert d["id"] == "m1"
    m2 = MessageSummary.from_dict(d)
    assert m2.id == "m1"


def test_message_detail_roundtrip():
    md = MessageDetail(id="m1", from_="a@b.com", to="me@me.com", date="2025-01-01T00:00:00Z", subject="s", body="b")
    d = md.to_dict()
    assert d["from_"] == "a@b.com"
    md2 = MessageDetail.from_dict(d)
    assert md2.body == "b"
