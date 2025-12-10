"""Global pytest configuration for slack_adapter tests.

Makes the generated client (clients/python/slack_chat_service_hw2_client)
importable so adapter.py can `from slack_chat_service_hw2_client.client import Client`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# tests/ -> slack_adapter/ -> src/ -> <repo root>
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CLIENTS_PATH = REPO_ROOT / "clients" / "python"

if str(CLIENTS_PATH) not in sys.path:
    sys.path.append(str(CLIENTS_PATH))
