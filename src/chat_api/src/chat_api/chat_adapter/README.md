# slack_adapter

Service-backed adapter that implements the `slack_api.ChatClient` contract and delegates
all operations to the local FastAPI Slack microservice (`slack_service`) via HTTP.

This package mirrors the structure and gates used in HW1/HW2 for consistency.

---

## 📦 Package layout

```
slack_adapter/
  pyproject.toml
  setup.py
  README.md
  src/slack_adapter/
    __init__.py
    adapter.py
    py.typed
  tests/
    test_adapter_contract.py
    test_adapter_client_cov.py
```

- **Public export:** `SlackServiceBackedClient` (re-exported at `slack_adapter` package root)
- **Typed package:** `py.typed` included
- **Single source of truth:** runtime code lives under `src/slack_adapter/`

---

## ✅ Contract implemented

The adapter fulfills `slack_api.ChatClient`:

- `health() -> bool`
- `list_channels() -> list[slack_api.Channel]`
- `post_message(channel_id: str, text: str) -> slack_api.Message`

> It **does not** call Slack directly. All work is delegated to `slack_service` REST endpoints.

---

## 🚀 Quick start

Install the three Slack packages in editable mode (order matters to satisfy imports):

```bash
python -m pip install -e src/slack_api
python -m pip install -e src/slack_service
python -m pip install -e src/slack_adapter
```

Use the adapter against a running service (or in tests, against the in‑process FastAPI app):

```python
from slack_adapter import SlackServiceBackedClient

with SlackServiceBackedClient(base_url="http://localhost:8000") as client:
    assert client.health()
    channels = client.list_channels()
    msg = client.post_message(channels[0].id, "hello from adapter")
    print(msg.ts)
```

---

## 🌐 Service contract (expected endpoints)

The adapter is tolerant to two JSON shapes for convenience:

### `GET /health`
- **200 OK** → the service is healthy.

### `GET /channels`
- Either a bare list: `[{ "id": "C001", "name": "general" }, ... ]`
- Or wrapped: `{ "channels": [ ... ] }`

### `POST /messages` (JSON: `{ "channel_id": "...", "text": "..." }`)
- Either a bare object: `{ "channel_id": "C001", "text": "hello", "ts": "..." }`
- Or wrapped: `{ "message": { ... } }`

---

## 🧪 Tests

Two layers to keep it light and deterministic:

1. **Contract/Import smoke** – `tests/test_adapter_contract.py`  
   Ensures public exports exist and type annotations align with `slack_api`.

2. **In‑memory integration** – `tests/test_adapter_client_cov.py`  
   Uses an **ASGI-to-sync transport** to exercise the adapter **against the real FastAPI app** in‑process
   (no network, no external Slack).

Run gates (same as HW1/HW2 style):

```bash
python -m ruff check --fix src/slack_adapter
python -m ruff check src/slack_adapter

python -m mypy src/slack_adapter

python -m pytest -q src/slack_adapter/tests
```

---

## ⚙️ Implementation notes

- HTTP client: `httpx.Client` (sync). For in‑process tests, we wrap `httpx.ASGITransport` so the sync client can call the async FastAPI app.
- Input/Output: adapter converts JSON payloads to `slack_api.Channel` / `slack_api.Message` using a helper that prefers `from_dict` if present, else `__init__(**kwargs)`.
- Fail‑fast: unexpected payload shapes raise `ValueError`.

---

## 🧩 Troubleshooting

- **`ModuleNotFoundError: slack_service` in tests**  
  Ensure `python -m pip install -e src/slack_service` before running adapter tests.

- **`httpx.ASGITransport` sync errors**  
  We use a tiny sync wrapper inside the tests to fully materialize async responses.

- **Mypy duplicate-module errors**  
  Keep the canonical inner layout only (`src/slack_adapter/src/slack_adapter`). Do not duplicate files at the outer level.

---

## 📝 PR checklist (copy/paste for reviews)

- [ ] Single `src/slack_adapter/src/slack_adapter` source of truth (no duplicates)
- [ ] `py.typed` present
- [ ] `ruff` clean
- [ ] `mypy` clean
- [ ] `pytest` all green locally
- [ ] README updated (this file)
- [ ] No Python/venv/CI changes compared to HW1/HW2