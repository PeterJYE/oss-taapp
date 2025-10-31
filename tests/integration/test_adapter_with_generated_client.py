"""Integration test: adapter talking to the local FastAPI service in-process.

This test uses FastAPI's TestClient base_url (http://testserver). The adapter
detects this and routes requests in-process via httpx's ASGI transport.
"""

from __future__ import annotations

import pytest

from openai_adapter import AdapterAPIError, OpenAIServiceAdapter

pytestmark = pytest.mark.integration


def test_adapter_end_to_end_against_app() -> None:
    """Start the FastAPI app and call it through the adapter using TestClient base URL."""
    try:
        from fastapi.testclient import TestClient  # type: ignore[assignment]
    except Exception:  # pragma: no cover - environment-dependent
        pytest.skip("fastapi or testclient not installed in this environment")

    from openai_client_service.main import app  # type: ignore[import-untyped]

    test_client = TestClient(app)
    base_url = str(test_client.base_url)

    adapter = OpenAIServiceAdapter(base_url=base_url, subject="it-user")

    # health should be OK
    assert adapter.health_check() is True

    # conversation lifecycle
    conv_id = adapter.create_conversation()
    assert isinstance(conv_id, str)
    assert conv_id

    data = adapter.get_conversation(conv_id)
    assert data.get("id") == conv_id

    assert adapter.delete_conversation(conv_id) is True

    # generate without API key should raise 401
    expected_status = 401
    with pytest.raises(AdapterAPIError) as ei:
        adapter.generate_response(["hello there"], conversation_id=None)
    assert ei.value.status_code == expected_status
