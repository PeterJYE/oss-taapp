# Slack Service

This package exposes a **FastAPI-based Slack Chat Service** for Homework 2 of the Open Source Software Product Development course (OSPSD).  
It serves as a microservice that wraps the core Slack implementation (`slack_impl`) and the abstract API contract (`slack_api`).

## 📘 Overview

The service provides REST endpoints that mirror the `ChatClient` interface defined in `slack_api`.  
It integrates with the `SlackClient` from `slack_impl` using dependency injection and exposes standard JSON responses.

## 🧩 Key Features

- `GET /health` — health check endpoint (returns `{ "ok": true }`)
- `GET /channels` — returns two deterministic channels (`C001`, `C002`)
- `POST /messages` — posts a message with `channel_id` and `text`, returning a JSON message object with a `ts`
- `GET /openapi.json` — serves the auto-generated OpenAPI schema for client generation

## 🧠 Dependencies

- **fastapi >= 0.115.0**
- **pydantic >= 2.7.0**
- **typing-extensions >= 4.9.0**
- Depends on local editable installs of:
  - `slack_api`
  - `slack_impl`

## ⚙️ Development Setup

From the repo root (not inside `src/`):

```bash
python -m pip install -e ./src/slack_api
python -m pip install -e ./src/slack_impl
python -m pip install -e ./src/slack_service
```

Then verify everything works:

```bash
python -m ruff check --fix src/slack_service
python -m mypy src/slack_service
python -m pytest -q src/slack_service/tests
```

## 🧪 Tests

Tests live under `src/slack_service/tests/` and include:

| Test File | Purpose |
|------------|----------|
| `test_health.py` | Checks `/health` returns `{ok: true}` |
| `test_channels.py` | Validates `/channels` returns two deterministic channels |
| `test_post_message.py` | Verifies `/messages` correctly returns a timestamped message |
| `test_openapi.py` | Ensures OpenAPI document exposes the expected paths |

All tests should pass with:

```bash
pytest -q src/slack_service/tests
```

## 🧾 License

This project is distributed under the **MIT License** as part of the NYU OSPSD course.