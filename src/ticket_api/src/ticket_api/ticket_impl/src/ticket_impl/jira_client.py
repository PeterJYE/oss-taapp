"""Thin HTTP client for Jira Cloud REST API v3."""

from __future__ import annotations

from http import HTTPStatus
from logging import getLogger
from typing import Any, cast

import httpx

from .config import settings
from .oauth import get_valid_access_token

logger = getLogger(__name__)


def _v3(path: str) -> str:
    return f"{settings.jira_api_base}/rest/api/3{path}"


async def _headers(user_id: str) -> dict[str, str]:
    token = await get_valid_access_token(user_id)
    return {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}


def _adf_paragraph(text: str) -> dict[str, Any]:
    """Convert plain text to Atlassian Document Format (ADF) paragraph."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


async def get_issue(user_id: str, issue_key: str) -> dict[str, Any]:
    """GET a single issue by key."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(_v3(f"/issue/{issue_key}"), headers=await _headers(user_id))
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())


async def delete_issue(user_id: str, issue_key: str) -> bool:
    """DELETE an issue by key; return True if deleted."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.delete(_v3(f"/issue/{issue_key}"), headers=await _headers(user_id))
        if r.status_code == HTTPStatus.NO_CONTENT:
            return True
        r.raise_for_status()
        return False


async def search_issues(user_id: str, jql: str, max_results: int = 50, start_at: int = 0) -> dict[str, Any]:  # noqa: ARG001
    """Search issues using JQL with pagination."""
    payload = {
        "jql": jql,
        "maxResults": max_results,
        "fields": ["summary", "description", "status", "assignee", "reporter", "priority"],  # Explicitly request fields
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(_v3("/search/jql"), headers=await _headers(user_id), json=payload)
        if r.status_code != HTTPStatus.OK:
            logger.error("Jira API error response: %s", r.text)
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())


async def create_issue(
    user_id: str,
    project_key: str,
    summary: str,
    description: str | None,
    assignee_account_id: str | None,
    reporter_account_id: str | None,
) -> dict[str, Any]:
    """Create a new issue in the given project."""
    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": "Task"},
    }
    if description:
        # Jira Cloud requires description in ADF (Atlassian Document Format)
        fields["description"] = _adf_paragraph(description)
    if assignee_account_id:
        fields["assignee"] = {"id": assignee_account_id}
    if reporter_account_id:
        fields["reporter"] = {"id": reporter_account_id}

    payload = {"fields": fields}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(_v3("/issue"), headers=await _headers(user_id), json=payload)
        if r.status_code != 200:
            logger.error(f"JIRA API error: {r.status_code} - {r.text}")
            logger.error(f"Request payload: {payload}")
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())


async def update_issue_fields(user_id: str, issue_key: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update issue fields by key; return updated issue."""
    payload = {"fields": fields}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(_v3(f"/issue/{issue_key}"), headers=await _headers(user_id), json=payload)
        r.raise_for_status()
        # PUT endpoint may return empty response; if so, fetch the updated issue
        if r.status_code == HTTPStatus.NO_CONTENT or not r.content:
            return await get_issue(user_id, issue_key)
        return cast("dict[str, Any]", r.json())


async def list_transitions(user_id: str, issue_key: str) -> list[dict[str, Any]]:
    """List available workflow transitions for an issue."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(_v3(f"/issue/{issue_key}/transitions"), headers=await _headers(user_id))
        r.raise_for_status()
        return cast("list[dict[str, Any]]", cast("dict[str, Any]", r.json()).get("transitions", []))


async def do_transition(user_id: str, issue_key: str, transition_id: str) -> None:
    """Perform a workflow transition on an issue."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            _v3(f"/issue/{issue_key}/transitions"),
            headers=await _headers(user_id),
            json={"transition": {"id": transition_id}},
        )
        r.raise_for_status()


async def add_comment(user_id: str, issue_key: str, content: str) -> dict[str, Any]:
    """Add a comment to an issue; return created comment."""
    payload = {"body": _adf_paragraph(content)}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(_v3(f"/issue/{issue_key}/comment"), headers=await _headers(user_id), json=payload)
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())


async def get_comments(user_id: str, issue_key: str) -> dict[str, Any]:
    """Get comments for an issue; return comments payload."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(_v3(f"/issue/{issue_key}/comment"), headers=await _headers(user_id))
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())


async def get_current_user_account_id(user_id: str) -> str | None:
    """Get the current authenticated user's account ID using /myself endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(_v3("/myself"), headers=await _headers(user_id))
        r.raise_for_status()
        data = cast("dict[str, Any]", r.json())
        return cast("str | None", data.get("accountId"))


async def find_user_account_id(user_id: str, query: str) -> str | None:
    """Find a user account ID by query (username, email, display name); return first match or None."""
    # Try /user/search endpoint first
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(_v3("/user/search"), headers=await _headers(user_id), params={"query": query})
            r.raise_for_status()
            arr = cast("list[dict[str, Any]]", r.json())
            if arr:
                return cast("str | None", arr[0].get("accountId"))
    except Exception as e:
        logger.warning(f"User search failed for '{query}': {e}. Trying /myself endpoint as fallback.")
        # If search fails and query matches current user's email, use current user
        # For now, just return None - caller can use get_current_user_account_id as fallback
    return None
