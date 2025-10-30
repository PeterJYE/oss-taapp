"""Integration test: adapter wired to the generated client talking to local FastAPI service.

This test will be skipped unless a generated client package is available
at `openai_client_service_api_client`. The repository includes a small helper
script to generate the client from the running service; if you run that
script locally this test will exercise the real client against the
TestClient-served FastAPI app.
"""

from __future__ import annotations

import importlib

import pytest

from ai_adapter import AIAdapter, AdapterError


pytestmark = pytest.mark.integration


def test_adapter_with_generated_client_end_to_end() -> None:
    """Start the FastAPI app and call it through the generated client via the adapter.

    The test will skip if the generated client package is not present. This
    makes the test safe to run in CI environments where client generation
    isn't performed.
    """
    try:
        client_mod = importlib.import_module("openai_client_service_api_client")
    except Exception:  # pragma: no cover - import-time behavior
        pytest.skip("generated client not available; run scripts/generate_client.py to generate it")

    Client = getattr(client_mod, "Client", None)
    if Client is None:  # pragma: no cover - defensive
        pytest.skip("generated client missing `Client` class; generation required")

    # Import the FastAPI app and serve it with TestClient. Importing
    # fastapi at collection time can fail in minimal environments, so do
    # the import lazily and skip if FastAPI isn't installed.
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception:  # pragma: no cover - environment-dependent
        pytest.skip("fastapi or testclient not installed in this environment")

    from openai_client_service.main import app  # type: ignore[import-untyped]

    test_client = TestClient(app)
    base_url = test_client.base_url

    # Create an instance of the generated client pointed at the TestClient base URL.
    # Different generated clients may accept different init args; we try common ones.
    try:
        gen_client = Client(base_url=base_url)  # type: ignore[arg-type]
    except TypeError:
        # Fallback: some generated clients accept a `base_url` kwarg or `url`.
        gen_client = Client(base_url=base_url)  # re-raise if this fails

    adapter = AIAdapter(client=gen_client)

    # At minimum, health_check should execute without raising an AdapterError.
    try:
        ok = adapter.health_check()
    except AdapterError as exc:
        pytest.fail(f"Adapter failed calling generated client: {exc}")

    assert isinstance(ok, bool)
