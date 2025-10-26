"""Minimal compatibility shim exposing MailClientAdapter for legacy tests.

This module lazily imports the real `ServiceClientAdapter` to avoid import-time
side effects during pytest collection. It provides the small interface older
tests expect (list_messages, get_message) and returns plain dictionaries.
"""
from __future__ import annotations

from typing import List, Dict


class MailClientAdapter:
    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        # Lazy import to avoid import-time side effects
        from adapter.service_client_adapter import ServiceClientAdapter

        self._svc = ServiceClientAdapter(base_url=base_url)

    def list_messages(self, max_results: int = 10) -> List[Dict[str, str]]:
        return [{"id": m.id, "subject": m.subject} for m in self._svc.get_messages(max_results=max_results)]

    def get_message(self, message_id: str) -> Dict[str, str]:
        m = self._svc.get_message(message_id)
        return {"id": m.id, "from_": m.from_, "to": m.to, "date": m.date, "subject": m.subject, "body": m.body}
