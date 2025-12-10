"""Pytest fixtures & test-time environment."""  # noqa: INP001

import os

# Set test env *before* importing anything that pulls ticket_impl.config
os.environ.setdefault("JIRA_CLOUD_ID", "00000000-0000-0000-0000-000000000000")
os.environ.setdefault("OAUTH_CLIENT_ID", "test-client-id")
os.environ.setdefault("OAUTH_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("OAUTH_REDIRECT_URI", "http://localhost/callback")
os.environ.setdefault("DB_URL", "sqlite:///./test_tokens.db")

# (keep the rest of your conftest; e.g., seed_token fixture)
import pytest
from ticket_impl.storage import upsert_tokens


@pytest.fixture
def seed_token() -> None:
    """Insert a valid token row for user u1."""
    upsert_tokens("u1", "ACCESS_TOKEN", "REFRESH_TOKEN", 3600)
