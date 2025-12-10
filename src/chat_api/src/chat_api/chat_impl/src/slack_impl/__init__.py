"""
Public surface for slack_impl.

- SlackClient: concrete client that can talk to Slack Web API (when configured)
- SQLiteTokenStore: DB-backed token store for OAuth credentials
- OAuth helpers: build_authorization_url, exchange_code_for_tokens
"""

from .slack_client import SlackClient
from .token_store import SQLiteTokenStore, TokenBundle
from .oauth import build_authorization_url, exchange_code_for_tokens

__all__ = [
    "SlackClient",
    "SQLiteTokenStore",
    "TokenBundle",
    "build_authorization_url",
    "exchange_code_for_tokens",
]
