"""End-to-end tests for real Gmail integration.

If the local mail service is not running this test should be skipped rather
than fail the entire pipeline. We treat connection errors as an indicator that
the environment does not have the service available.
"""

import pytest
import httpx

from adapter.service_client_adapter import ServiceClientAdapter


@pytest.mark.e2e
def test_real_gmail_flow() -> None:
    """Test real Gmail flow with actual API calls or skip when unreachable."""
    adapter = ServiceClientAdapter(base_url="http://localhost:8000")
    try:
        msgs = list(adapter.get_messages())
    except (httpx.HTTPError, ConnectionError):  # pragma: no cover - network dependent
        pytest.skip("Skipping real Gmail flow: service not reachable on localhost:8000")
        return
    assert isinstance(msgs, list)
    if msgs:
        msg_id = msgs[0].id
        detail = adapter.get_message(msg_id)
        assert detail.subject is not None
