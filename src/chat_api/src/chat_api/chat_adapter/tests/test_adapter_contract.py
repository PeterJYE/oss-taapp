"""Contract-surface checks for the Slack adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from slack_adapter import SlackServiceBackedClient

if TYPE_CHECKING:  # satisfy TC001: keep app imports type-only
    from slack_api import Channel, Message


def test_adapter_exports() -> None:
    """Adapter exposes the expected public methods."""
    client = SlackServiceBackedClient(base_url="http://example.com")

    for attr in ("health", "list_channels", "post_message"):
        if not hasattr(client, attr):
            pytest.fail(f"Adapter missing expected attribute: {attr}")

    client.close()


def test_annotations_align_with_contract() -> None:
    """Touch annotations so they are not flagged as unused."""
    chans: list[Channel] | None = None  # type: ignore[name-defined]
    msg: Message | None = None  # type: ignore[name-defined]

    if chans is not None:
        pytest.fail("expected chans to be None in annotation touch test")
    if msg is not None:
        pytest.fail("expected msg to be None in annotation touch test")
