"""End-to-end tests for real Gmail integration."""

from __future__ import annotations

import os

import pytest

from adapter.service_client_adapter import ServiceClientAdapter


@pytest.mark.e2e
def test_real_gmail_flow() -> None:
    """Test real Gmail flow with actual API calls."""
    if not os.getenv("RUN_REAL_GMAIL_E2E"):
        pytest.skip("Real Gmail E2E requires RUN_REAL_GMAIL_E2E=1")

    base_url = os.getenv("GMAIL_E2E_BASE_URL", "http://localhost:8000")
    adapter = ServiceClientAdapter(base_url=base_url)
    msgs = list(adapter.get_messages())
    assert isinstance(msgs, list)
    if msgs:
        msg_id = msgs[0].id
        detail = adapter.get_message(msg_id)
        assert detail.subject is not None
