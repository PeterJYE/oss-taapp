"""Persistence helpers: OAuth tokens and (uuid ↔ Jira key) mapping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import settings

if TYPE_CHECKING:
    from uuid import UUID


class Base(DeclarativeBase):
    """SQLAlchemy base."""


class Token(Base):
    """Stored OAuth tokens for a user."""

    __tablename__ = "jira_oauth_tokens"
    user_id: Mapped[str] = mapped_column(primary_key=True)
    access_token: Mapped[str]
    refresh_token: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TicketMap(Base):
    """Stable mapping between domain Ticket.id (UUID) and Jira issue key.

    We also scope by user_id to support multi-tenant scenarios cleanly.
    """

    __tablename__ = "ticket_map"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str]
    ticket_uuid: Mapped[str]  # store as stringified UUID
    jira_key: Mapped[str]
    __table_args__ = (UniqueConstraint("user_id", "ticket_uuid", name="uq_user_ticket"),)


engine = create_engine(settings.db_url, future=True)
Base.metadata.create_all(engine)


# --- tokens ---
def upsert_tokens(user_id: str, access: str, refresh: str, expires_in_sec: int) -> None:
    """Insert/update tokens for a user with a fresh expiry."""
    now = datetime.now(tz=UTC)
    expires_at = now + timedelta(seconds=expires_in_sec)
    with Session(engine) as s:
        tok = s.get(Token, user_id)
        if not tok:
            tok = Token(user_id=user_id, access_token=access, refresh_token=refresh, expires_at=expires_at)
        else:
            tok.access_token, tok.refresh_token, tok.expires_at = access, refresh, expires_at
        s.add(tok)
        s.commit()


def get_tokens(user_id: str) -> Token | None:
    """Fetch tokens row for a user, if any."""
    with Session(engine) as s:
        return s.get(Token, user_id)


def get_user_tokens(user_id: str) -> dict[str, str] | None:
    """Get user tokens as a dictionary (for service layer compatibility).

    Returns:
        Dictionary with 'access_token' and 'refresh_token' keys, or None if not found.

    """
    tok = get_tokens(user_id)
    if not tok:
        return None
    return {
        "access_token": tok.access_token,
        "refresh_token": tok.refresh_token,
    }


def clear_user_tokens(user_id: str) -> bool:
    """Delete all tokens for a user.

    Args:
        user_id: The user ID whose tokens should be deleted.

    Returns:
        True if tokens were deleted, False if user had no tokens.

    """
    with Session(engine) as s:
        tok = s.get(Token, user_id)
        if not tok:
            return False
        s.delete(tok)
        s.commit()
        return True


def update_access(user_id: str, access: str, expires_in_sec: int) -> None:
    """Update only the access token and expiry."""
    now = datetime.now(tz=UTC)
    with Session(engine) as s:
        tok = s.get(Token, user_id)
        if not tok:
            return
        tok.access_token = access
        tok.expires_at = now + timedelta(seconds=expires_in_sec)
        s.add(tok)
        s.commit()


def is_expired(tok: Token) -> bool:
    """Return True if token expiry is in the past."""
    exp = tok.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    return exp <= datetime.now(tz=UTC)


# --- mapping ---
def map_uuid_to_key(user_id: str, ticket_uuid: UUID, jira_key: str) -> None:
    """Upsert a single (uuid → key) mapping."""
    with Session(engine) as s:
        exists = s.execute(
            select(TicketMap).where(
                TicketMap.user_id == user_id,
                TicketMap.ticket_uuid == str(ticket_uuid),
            ),
        ).scalar_one_or_none()
        if exists:
            exists.jira_key = jira_key
            s.add(exists)
        else:
            s.add(TicketMap(user_id=user_id, ticket_uuid=str(ticket_uuid), jira_key=jira_key))
        s.commit()


def get_key_for_uuid(user_id: str, ticket_uuid: UUID) -> str | None:
    """Resolve a domain UUID to its Jira key for a given user."""
    with Session(engine) as s:
        return s.execute(
            select(TicketMap.jira_key).where(
                TicketMap.user_id == user_id,
                TicketMap.ticket_uuid == str(ticket_uuid),
            ),
        ).scalar_one_or_none()


def ensure_mapping_for_keys(user_id: str, pairs: list[tuple[UUID, str]]) -> None:
    """Bulk upsert of (uuid, jira_key) pairs to keep list operations consistent."""
    with Session(engine) as s:
        for ticket_uuid, jira_key in pairs:
            row = s.execute(
                select(TicketMap).where(
                    TicketMap.user_id == user_id,
                    TicketMap.ticket_uuid == str(ticket_uuid),
                ),
            ).scalar_one_or_none()
            if row:
                row.jira_key = jira_key
                s.add(row)
            else:
                s.add(TicketMap(user_id=user_id, ticket_uuid=str(ticket_uuid), jira_key=jira_key))
        s.commit()
