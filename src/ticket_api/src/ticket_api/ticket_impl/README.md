# Ticket Implementation

Jira Cloud implementation of `TicketServiceAPI` with OAuth 2.0 authentication.

## Purpose

- Implements `TicketServiceAPI` for Jira Cloud REST API v3
- OAuth 2.0 (3-legged) authentication with automatic token refresh
- UUID abstraction (hides Jira issue keys)
- SQLAlchemy-based token and mapping storage

## Installation

```bash
uv add ticket-impl
```

## Configuration

Set environment variables:

```bash
OAUTH_CLIENT_ID="your-jira-oauth-client-id"
OAUTH_CLIENT_SECRET="your-jira-oauth-client-secret"
OAUTH_REDIRECT_URI="http://localhost:8000/api/v1/auth/callback"
JIRA_CLOUD_ID="your-jira-cloud-id"
DB_URL="sqlite:///./tickets.db"  # or postgresql://...
```

## Usage

```python
from ticket_impl import TicketImpl

service = TicketImpl(user_id="user-123", project_key="PROJ")

ticket = await service.create_ticket(
    title="Bug Report",
    description="Found an issue",
    reporter="user@example.com"
)
```

## OAuth Flow

1. User visits `/api/v1/auth/login`
2. Redirects to Jira authorization page
3. User grants permission
4. Callback to `/api/v1/auth/callback` with code
5. Exchange code for access/refresh tokens
6. Store tokens in database
7. Automatic refresh when expired

## Components

- `impl.py` - Main `TicketImpl` class
- `jira_client.py` - Low-level Jira REST API calls
- `oauth.py` - OAuth 2.0 flow and token management
- `storage.py` - SQLAlchemy models and database operations
- `config.py` - Environment configuration

## Key Features

**UUID Abstraction:** Uses UUID v5 (deterministic) to hide Jira issue keys from domain layer.

**ADF Support:** Converts plain text to Atlassian Document Format for rich text.

**Token Management:** Automatic refresh before expiration, stored securely in database.

**Error Handling:** Maps Jira errors to domain exceptions (`ServiceError`, `TicketNotFoundError`).

## Testing

```bash
uv run pytest src/ticket_impl/tests/ -v
```

**Coverage:** 95%+ (30+ tests)

All tests mock Jira API calls - no real network requests.
