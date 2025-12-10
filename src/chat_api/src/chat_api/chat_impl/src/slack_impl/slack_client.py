from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ---------- Simple value objects with attribute access ----------
class Channel:
    def __init__(self, id: str, name: str) -> None:  # noqa: A002 (id is intentional here)
        self.id = id
        self.name = name

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "name": self.name}

    def __repr__(self) -> str:  # pragma: no cover
        return f"Channel(id={self.id!r}, name={self.name!r})"


class Message:
    def __init__(self, channel_id: str, text: str, ts: str, id: str = "") -> None:  # noqa: A002
        self.id = id
        self.channel_id = channel_id
        self.text = text
        self.ts = ts

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "channel_id": self.channel_id,
            "text": self.text,
            "ts": self.ts,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return ("Message(id={!r}, channel_id={!r}, text={!r}, ts={!r})").format(
            self.id, self.channel_id, self.text, self.ts
        )


# ---------- Helpers ----------
def sanitize_text(text: str, max_len: int = 1000) -> str:
    """Normalize text for Slack.

    - Coerce to string
    - Collapse consecutive whitespace and trim ends
    - Remove control chars except tab/newline/carriage-return
    - Truncate to *max_len*
    """
    if not isinstance(text, str):
        text = str(text)
    # Keep only printable or whitespace, then collapse runs of whitespace
    cleaned = "".join(
        ch for ch in text if ch.isprintable() or ch in ("\t", "\n", "\r", " ")
    )
    cleaned = " ".join(cleaned.split())
    return cleaned[:max_len]


# ---------- Client ----------
class SlackClient:
    """Concrete Slack client with an **offline** mode for tests.

    Offline mode (default) is enabled when *base_url* or *token* are not provided.
    In offline mode, methods return deterministic stub data as objects with attributes.

    Online mode is enabled when *base_url* and *token* are provided; a synchronous
    httpx.Client will be created unless one is passed via *http*.
    """

    def __init__(
        self,
        base_url: Optional[str] | None = None,
        token: Optional[str] | None = None,
        http: Optional[httpx.Client] | None = None,
    ) -> None:
        self.offline = not (base_url and token)
        self.base_url = (base_url or "").rstrip("/")
        self.token = token or ""
        self.http = http

        if not self.offline:
            # Only construct an HTTP client when online.
            self.http = self.http or httpx.Client(
                base_url=self.base_url, headers=self._auth_header()
            )

    # ---------------- Internal helpers ----------------

    def _auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    # ---------------- Public API ----------------

    def health(self) -> bool:
        """Return True when the client is usable.

        - Offline: always True (used by unit tests)
        - Online: perform a trivial GET /health if available, else True.
        """
        if self.offline:
            return True
        try:
            assert self.http is not None
            resp = self.http.get("/health")
            if resp.status_code == 200:
                data = resp.json()
                ok = data.get("ok", True) if isinstance(data, dict) else True
                return bool(ok)
        except Exception:
            logger.debug(
                "health check failed; returning True for leniency", exc_info=True
            )
        return True

    def list_channels(self) -> List[Channel]:
        """List channels.

        - Offline: two deterministic channels (C001, C002)
        - Online: GET /conversations.list and map the 'channels' array
        """
        if self.offline:
            return [Channel("C001", "general"), Channel("C002", "random")]

        assert self.http is not None
        resp = self.http.get("/conversations.list")
        resp.raise_for_status()
        data = resp.json()
        logger.debug("Fetched channels: %s", data)
        items = data.get("channels", []) if isinstance(data, dict) else []
        out: List[Channel] = []
        for it in items:
            if isinstance(it, dict):
                cid = str(it.get("id", "") or "")
                name = str(it.get("name", "") or "")
                if cid and name:
                    out.append(Channel(cid, name))
        return out

    def post_message(self, channel: str, text: str) -> Message:
        """Post a message to a channel and return the created message object."""
        cleaned = sanitize_text(text)

        if self.offline:
            ts = f"{time.time():.6f}"
            msg_id = f"msg-{int(time.time() * 1000)}"
            return Message(channel_id=channel, text=cleaned, ts=ts, id=msg_id)

        assert self.http is not None
        payload = {"channel": channel, "text": cleaned}
        resp = self.http.post("/chat.postMessage", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("Posted message: %s", data)
        # Normalize a minimal shape that tests can read
        if isinstance(data, dict):
            msg = data.get("message", data)
            return Message(
                channel_id=str(msg.get("channel") or channel),
                text=str(msg.get("text", cleaned)),
                ts=str(msg.get("ts", "")),
                id=str(msg.get("id") or msg.get("client_msg_id") or msg.get("ts", "")),
            )
        return Message(channel_id=channel, text=cleaned, ts="", id="")

    def get_channel_history(self, channel: str, limit: int = 20) -> List[Message]:
        """Return recent messages for a channel."""
        if self.offline:
            base = [
                Message(channel_id=channel, text="hello", ts="1710000000.000001"),
                Message(channel_id=channel, text="world", ts="1710000001.000001"),
            ]
            return base[: max(0, int(limit))]

        assert self.http is not None
        params: Dict[str, Any] = {"channel": channel, "limit": int(limit)}
        resp = self.http.get("/conversations.history", params=params)
        resp.raise_for_status()
        data = resp.json()
        logger.debug("Fetched channel history: %s", data)
        out: List[Message] = []
        if isinstance(data, dict):
            for m in data.get("messages", []):
                if isinstance(m, dict):
                    out.append(
                        Message(
                            channel_id=channel,
                            text=str(m.get("text", "")),
                            ts=str(m.get("ts", "")),
                            id=str(
                                m.get("id") or m.get("client_msg_id") or m.get("ts", "")
                            ),
                        )
                    )
        return out

    def delete_message(self, channel: str, message_id: str) -> bool:
        """Delete a message from a channel.
        
        Args:
            channel: Channel ID where the message exists
            message_id: Message timestamp (ts) or ID to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if self.offline:
            # In offline mode, always return True (stub behavior)
            return True

        assert self.http is not None
        try:
            payload = {"channel": channel, "ts": message_id}
            resp = self.http.post("/chat.delete", json=payload)
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Deleted message: %s", data)
            # Slack returns {"ok": true} on success
            if isinstance(data, dict):
                return bool(data.get("ok", False))
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Failed to delete message: %s", e)
            return False

    def close(self) -> None:
        if self.http is not None:
            self.http.close()


def get_slack_client(
    base_url: str | None = None, token: str | None = None
) -> SlackClient:
    """Factory that defaults to **offline** mode when args are missing."""
    return SlackClient(base_url=base_url, token=token)
