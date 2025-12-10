"""Concrete implementation of the Ticket API that talks to Jira Cloud."""

from __future__ import annotations

import logging
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

# Import internal APIs from parent ticket_impl folder
import sys
from pathlib import Path

_parent = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_parent))

# ruff: noqa: E402  # Module level import not at top of file (needed for sys.path manipulation)
from ticket_api.ticket_impl.interface import TicketServiceAPI  # typeqa: ignore[import-untyped]
from ticket_api.ticket_impl.models import (  # type: ignore[import-untyped]
    Comment,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from ticket_api.ticket_impl.exceptions import ServiceError, TicketNotFoundError  # type: ignore[import-untyped]

from . import jira_client as jc
from .storage import ensure_mapping_for_keys, get_key_for_uuid, map_uuid_to_key

logger = logging.getLogger(__name__)

# ---- mapping helpers ----


def _priority_to_jira(p: TicketPriority) -> str:
    return {
        TicketPriority.LOW: "Low",
        TicketPriority.MEDIUM: "Medium",
        TicketPriority.HIGH: "High",
        TicketPriority.CRITICAL: "Highest",
    }[p]


def _status_name_to_domain(name: str | None) -> TicketStatus:
    if not name:
        return TicketStatus.OPEN
    k = name.strip().lower().replace("-", "_").replace(" ", "_")
    if k in {"open", "to_do"}:
        return TicketStatus.OPEN
    if k in {"in_progress", "doing"}:
        return TicketStatus.IN_PROGRESS
    if k in {"done", "resolved"}:
        return TicketStatus.RESOLVED
    if k == "closed":
        return TicketStatus.CLOSED
    return TicketStatus.OPEN


def _jira_to_ticket(data: dict[str, Any], user_id: str) -> Ticket:
    fields = data.get("fields", {})
    key = data.get("key", "")
    status_name = (fields.get("status") or {}).get("name")
    priority_name = (fields.get("priority") or {}).get("name", "Medium")

    # domain priority best-effort reverse map
    pr_map = {
        "low": TicketPriority.LOW,
        "medium": TicketPriority.MEDIUM,
        "high": TicketPriority.HIGH,
        "highest": TicketPriority.CRITICAL,
    }
    domain_priority = pr_map.get(str(priority_name).lower(), TicketPriority.MEDIUM)

    # stable UUID for this user+key; also store mapping (impl never leaks Jira key)
    ticket_uuid = uuid5(NAMESPACE_URL, f"{user_id}:{key}")
    map_uuid_to_key(user_id, ticket_uuid, key)

    return Ticket(
        id=ticket_uuid,
        title=fields.get("summary", ""),
        description=(fields.get("description") or "")
        if isinstance(fields.get("description"), str)
        else str(fields.get("description") or ""),
        status=_status_name_to_domain(status_name),
        priority=domain_priority,
        assignee=(fields.get("assignee") or {}).get("displayName"),
        reporter=(fields.get("reporter") or {}).get("displayName") or "",
    )


def _jira_comment_to_domain(c: dict[str, Any], ticket_uuid: UUID) -> Comment:
    text = ""
    body = c.get("body") or {}
    if isinstance(body, dict):
        for block in body.get("content", []):
            if block.get("type") == "paragraph":
                for node in block.get("content", []):
                    if node.get("type") == "text":
                        text += node.get("text", "")
                text += "\n"
    return Comment(
        id=uuid5(NAMESPACE_URL, f"comment:{c.get('id', '')}"),
        ticket_id=ticket_uuid,
        author=(c.get("author") or {}).get("displayName") or "unknown",
        content=(text.strip() or "<empty>"),
    )


# ---- concrete implementation ----


class TicketImpl(TicketServiceAPI):
    """Jira-backed implementation of the TicketServiceAPI.

    All methods are async and map domain UUIDs to Jira issue keys internally.
    """

    def __init__(self, user_id: str, project_key: str) -> None:
        """Initialize with a Jira-authorized user and a default project key."""
        self.user_id = user_id
        self.project_key = project_key

    # CREATE
    async def create_ticket(
        self,
        title: str,
        description: str,
        reporter: str,
        priority: TicketPriority = TicketPriority.MEDIUM,
        assignee: str | None = None,
    ) -> Ticket:
        """Create a ticket and return its hydrated domain model."""
        try:
            # Try to find reporter account ID, fallback to current authenticated user if search fails
            reporter_id = None
            if reporter:
                reporter_id = await jc.find_user_account_id(self.user_id, reporter)
                # If user search fails (endpoint not available), use current authenticated user as reporter
                if not reporter_id:
                    reporter_id = await jc.get_current_user_account_id(self.user_id)
                    logger.info(f"Using current authenticated user as reporter (search for '{reporter}' failed)")
            assignee_id = await jc.find_user_account_id(self.user_id, assignee) if assignee else None

            created = await jc.create_issue(
                user_id=self.user_id,
                project_key=self.project_key,
                summary=title,
                description=description,
                assignee_account_id=assignee_id,
                reporter_account_id=reporter_id,
            )

            key = created["key"]
            # update priority if needed
            if priority != TicketPriority.MEDIUM:
                await jc.update_issue_fields(self.user_id, key, {"priority": {"name": _priority_to_jira(priority)}})

            data = await jc.get_issue(self.user_id, key)
            return _jira_to_ticket(data, self.user_id)
        except Exception as e:
            msg = f"Failed to create ticket: {e}"
            raise ServiceError(msg) from e

    # READ ONE
    async def get_ticket(self, ticket_id: UUID) -> Ticket:
        """Get a single ticket by domain UUID; raise if not found."""
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        try:
            data = await jc.get_issue(self.user_id, key)
        except Exception as e:
            raise TicketNotFoundError(ticket_id) from e
        return _jira_to_ticket(data, self.user_id)

    # LIST (with basic filters → JQL)
    async def list_tickets(
        self,
        status: TicketStatus | None = None,
        assignee: str | None = None,
        reporter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        """List tickets with simple filters using JQL."""
        if limit < 0 or offset < 0:
            msg = "limit/offset must be non-negative."
            raise ValueError(msg)

        clauses: list[str] = [f'project = "{self.project_key}"']
        if status:
            name = {
                TicketStatus.OPEN: "Open",
                TicketStatus.IN_PROGRESS: "In Progress",
                TicketStatus.RESOLVED: "Done",
                TicketStatus.CLOSED: "Closed",
            }[status]
            clauses.append(f'status = "{name}"')
        if assignee:
            clauses.append(f'assignee in (currentUser(), "{assignee}")')
        if reporter:
            clauses.append(f'reporter = "{reporter}"')

        jql = " AND ".join(clauses) + " ORDER BY updated DESC"
        try:
            raw = await jc.search_issues(self.user_id, jql=jql, max_results=min(50, limit), start_at=offset)
            logger.debug("Jira search raw response: %s", raw)
        except Exception as e:
            msg = f"Failed to list tickets: {e}"
            raise ServiceError(msg) from e

        # The /search/jql endpoint returns issues directly in the response
        issues = raw.get("issues", [])
        logger.info("Jira search returned %d issues", len(issues))

        out: list[Ticket] = []
        pairs: list[tuple[UUID, str]] = []
        for it in issues:
            t = _jira_to_ticket(it, self.user_id)
            out.append(t)
            pairs.append((t.id, it.get("key", "")))
        ensure_mapping_for_keys(self.user_id, pairs)
        return out

    # UPDATE
    async def update_ticket(
        self,
        ticket_id: UUID,
        _title: str | None = None,
        _description: str | None = None,
        status: TicketStatus | None = None,
        _priority: TicketPriority | None = None,
        _assignee: str | None = None,
    ) -> Ticket:
        """Update fields and/or workflow state; return the refreshed ticket."""
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        try:
            if status:
                transitions = await jc.list_transitions(self.user_id, key)
                target = {
                    TicketStatus.OPEN: {"Open", "To Do"},
                    TicketStatus.IN_PROGRESS: {"In Progress", "Doing"},
                    TicketStatus.RESOLVED: {"Done", "Resolved"},
                    TicketStatus.CLOSED: {"Closed"},
                }[status]
                choice = next((t for t in transitions if t.get("name") in target), None)
                if not choice:
                    msg = f"No valid transition found to {status} for {key}"
                    raise ServiceError(msg)  # noqa: TRY301
                await jc.do_transition(self.user_id, key, choice["id"])
            data = await jc.get_issue(self.user_id, key)
            return _jira_to_ticket(data, self.user_id)
        except TicketNotFoundError:
            raise
        except Exception as e:
            msg = f"Failed to transition status: {e}"
            raise ServiceError(msg) from e

    async def reassign_ticket(self, ticket_id: UUID, new_assignee: str) -> Ticket:
        """Reassign the ticket to a new assignee and return the updated ticket."""
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        try:
            acct = await jc.find_user_account_id(self.user_id, new_assignee)
            if not acct:
                msg = f"Assignee '{new_assignee}' was not found"
                raise ServiceError(msg)  # noqa: TRY301
            await jc.update_issue_fields(self.user_id, key, {"assignee": {"id": acct}})
            data = await jc.get_issue(self.user_id, key)
            return _jira_to_ticket(data, self.user_id)
        except TicketNotFoundError:
            raise
        except Exception as e:
            msg = f"Failed to reassign ticket: {e}"
            raise ServiceError(msg) from e

    async def update_priority(self, ticket_id: UUID, new_priority: TicketPriority) -> Ticket:
        """Update the ticket priority and return the updated ticket."""
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        try:
            await jc.update_issue_fields(self.user_id, key, {"priority": {"name": _priority_to_jira(new_priority)}})
            data = await jc.get_issue(self.user_id, key)
            return _jira_to_ticket(data, self.user_id)
        except TicketNotFoundError:
            raise
        except Exception as e:
            msg = f"Failed to update priority: {e}"
            raise ServiceError(msg) from e

    async def update_description(self, ticket_id: UUID, new_description: str) -> Ticket:
        """Update the ticket description and return the updated ticket."""
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        try:
            await jc.update_issue_fields(self.user_id, key, {"description": new_description})
            data = await jc.get_issue(self.user_id, key)
        except Exception as e:
            raise TicketNotFoundError(ticket_id) from e

        return _jira_to_ticket(data, self.user_id)

    # DELETE
    async def delete_ticket(self, ticket_id: UUID) -> bool:
        """Delete a ticket by UUID mapped to a Jira issue key."""
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        try:
            return await jc.delete_issue(self.user_id, key)
        except Exception as e:
            msg = f"Failed to delete ticket: {e}"
            raise ServiceError(msg) from e

    # COMMENTS
    async def add_comment(self, ticket_id: UUID, author: str, content: str) -> Comment:  # noqa: ARG002
        """Add a comment and return it in domain form.

        Note: The author parameter is not used because Jira automatically assigns
        comments to the authenticated user making the API call.
        """
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        try:
            data = await jc.add_comment(self.user_id, key, content)
        except Exception as e:
            raise TicketNotFoundError(ticket_id) from e

        return _jira_comment_to_domain(data, ticket_id)

    async def get_ticket_comments(self, ticket_id: UUID) -> list[Comment]:
        """Return all comments for a ticket as domain objects."""
        key = get_key_for_uuid(self.user_id, ticket_id) or str(ticket_id)
        raw = await jc.get_comments(self.user_id, key)
        comments = raw.get("comments", [])
        return [_jira_comment_to_domain(c, ticket_id) for c in comments]

    async def transition_status(self, ticket_id: UUID, new_status: TicketStatus) -> Ticket:
        """Transition the ticket to a new status and return the updated ticket."""
        return await self.update_ticket(ticket_id, status=new_status)
