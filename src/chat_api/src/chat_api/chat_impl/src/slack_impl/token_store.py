from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class TokenBundle:
    """A minimal bundle for storing OAuth tokens in a DB."""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    scope: Optional[str] = None
    expires_at: Optional[float] = None  # epoch seconds, if you manage expiry


class SQLiteTokenStore:
    """SQLite-backed token store that satisfies HW2's 'securely store in a database'.

    IMPORTANT: Uses a single connection per instance so that ':memory:' works
    across all calls. Opening a new connection for ':memory:' would create a new,
    empty database each time.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        # keep one connection for the life of the store
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tokens (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_type TEXT NOT NULL,
                scope TEXT,
                expires_at REAL
            )
            """
        )
        self._conn.commit()

    def save(self, user_id: str, bundle: TokenBundle) -> None:
        self._conn.execute(
            """
            INSERT INTO tokens(user_id, access_token, refresh_token, token_type, scope, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                token_type=excluded.token_type,
                scope=excluded.scope,
                expires_at=excluded.expires_at
            """,
            (
                user_id,
                bundle.access_token,
                bundle.refresh_token,
                bundle.token_type,
                bundle.scope,
                bundle.expires_at,
            ),
        )
        self._conn.commit()

    def load(self, user_id: str) -> Optional[TokenBundle]:
        cur = self._conn.execute(
            "SELECT access_token, refresh_token, token_type, scope, expires_at FROM tokens WHERE user_id=?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        access, refresh, ttype, scope, exp = row
        return TokenBundle(
            access_token=str(access),
            refresh_token=str(refresh) if refresh is not None else None,
            token_type=str(ttype) if ttype else "Bearer",
            scope=str(scope) if scope is not None else None,
            expires_at=float(exp) if exp is not None else None,
        )

    def delete(self, user_id: str) -> None:
        self._conn.execute("DELETE FROM tokens WHERE user_id=?", (user_id,))
        self._conn.commit()

    def has(self, user_id: str) -> bool:
        cur = self._conn.execute("SELECT 1 FROM tokens WHERE user_id=?", (user_id,))
        return cur.fetchone() is not None

    def clear(self) -> None:
        self._conn.execute("DELETE FROM tokens")
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
