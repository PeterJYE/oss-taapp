import pytest
from mail_client_adapter import MailClientAdapter


@pytest.mark.e2e
def test_real_gmail_flow():
    adapter = MailClientAdapter(base_url="http://localhost:8000")  
    msgs = adapter.list_messages()
    assert isinstance(msgs, list)
    if msgs:
        msg_id = msgs[0]["id"]
        detail = adapter.get_message(msg_id)
        assert "subject" in detail
