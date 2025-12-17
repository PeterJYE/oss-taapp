# slack_impl

Concrete Slack implementation for HW2 (OSPSD Team 4).

- **`SlackClient`** — concrete client implementing `slack_api.ChatClient`
  - **Offline mode (default):** deterministic results, zero network
  - **Online mode:** pass a Slack token to call Slack Web API
- **`SQLiteTokenStore`** — DB-backed OAuth token store (SQLite)
- **OAuth helpers** — `build_authorization_url`, `exchange_code_for_tokens`

> This package is laid out as a `src/` package. Install it in editable mode from the monorepo root.

---

## Install (editable)

```bash
python -m pip install -e src/slack_impl
```

## Runtime env (for OAuth / online mode)

Set these before using OAuth or live Slack calls:

- `SLACK_CLIENT_ID`
- `SLACK_CLIENT_SECRET`
- `SLACK_REDIRECT_URI` (e.g., `http://localhost:8000/oauth/callback`)
- `SLACK_SCOPES` (space-delimited, e.g., `chat:write channels:read`)

For **online** API calls, provide a token (bot/user):

```python
from slack_impl import SlackClient

client = SlackClient(default_access_token="xoxb-xxxxxxxx")  # enables online mode
channels = client.list_channels()           # Slack conversations.list
sent = client.post_message(channels[0].id, "Hello from HW2!")  # chat.postMessage
```

---

## Offline (deterministic, test-friendly) example

```python
from slack_impl import SlackClient

client = SlackClient()       # no token -> offline mode
assert client.health() is True
chs = client.list_channels() # -> [C001 "general", C002 "random"]
msg = client.post_message("C001", "  hello   world ")
print(msg)                   # ts is a stable, non-empty string
```

---

## OAuth helpers (service will wire endpoints)

```python
import secrets
from slack_impl import (
  build_authorization_url,
  exchange_code_for_tokens,
  SQLiteTokenStore, TokenBundle
)

state = secrets.token_urlsafe(16)
auth_url = build_authorization_url(state)   # send user here

# In your callback handler (after Slack redirects back with ?code=...):
# tokens = await exchange_code_for_tokens(code)
# SQLiteTokenStore().save(user_id, tokens)
```

---

## Token store (SQLite)

```python
from slack_impl import SQLiteTokenStore, TokenBundle

store = SQLiteTokenStore()  # ":memory:" by default
bundle = TokenBundle(access_token="xoxb-abc", scope="chat:write")
store.save("U123", bundle)
assert store.has("U123") is True
assert store.load("U123") == bundle
store.delete("U123")
```

---

## Development

Run gates from repo root:

```bash
python -m ruff check --fix src/slack_impl && python -m ruff check src/slack_impl
python -m mypy src/slack_impl
python -m pytest -q src/slack_impl/tests
```

**Notes**
- Package data includes `py.typed` for PEP 561 typing.
- Online mode uses `httpx` lazily; offline mode has no network dependency.

---

## What’s implemented (HW2-aligned)

- ✅ Concrete client fulfilling `slack_api.ChatClient`
- ✅ Deterministic offline behavior for tests
- ✅ Online Web API calls for `conversations.list` and `chat.postMessage` (when token provided)
- ✅ OAuth helpers (authorize URL + token exchange)
- ✅ DB-backed token storage (SQLite, `:memory:` supported)
