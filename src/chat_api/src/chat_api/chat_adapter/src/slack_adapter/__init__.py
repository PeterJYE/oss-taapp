"""Public API surface for the slack_adapter package."""

from __future__ import annotations

from slack_api import Channel, Message

from .adapter import (
    ServiceAdapter,
    ServiceBackedClient,
    SlackServiceBackedClient,
    _get_id,
)

# Explicit public API (sorted for Ruff RUF022)
__all__ = [
    "Channel",
    "Message",
    "ServiceAdapter",
    "ServiceBackedClient",
    "SlackServiceBackedClient",
    "_get_id",
]
