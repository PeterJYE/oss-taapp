"""End-to-end tests for real Gmail integration."""

import pytest

from adapter.service_client_adapter import ServiceClientAdapter


@pytest.mark.e2e
def test_real_gmail_flow() -> None:
    """Test real Gmail flow with actual API calls."""
    adapter = ServiceClientAdapter(base_url="http://localhost:8000")
    msgs = list(adapter.get_messages())
    assert isinstance(msgs, list)
    if msgs:
        msg_id = msgs[0].id
        detail = adapter.get_message(msg_id)
        assert detail.subject is not None
