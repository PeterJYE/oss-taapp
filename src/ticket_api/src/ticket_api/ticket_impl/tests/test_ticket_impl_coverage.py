"""Additional tests to improve coverage for TicketImpl and jira_client.

These tests focus on covering missing lines to bring overall coverage above 85%.
"""

import re
from uuid import uuid4

import httpx
import pytest
import respx
from ticket_api.ticket_impl.exceptions import ServiceError, TicketNotFoundError
from ticket_api.ticket_impl.models import TicketPriority, TicketStatus
from ticket_impl import TicketImpl
from ticket_impl.config import settings
from ticket_impl.impl import _jira_to_ticket, _priority_to_jira, _status_name_to_domain
from ticket_impl.jira_client import (
    _adf_paragraph,
    add_comment,
    create_issue,
    delete_issue,
    do_transition,
    find_user_account_id,
    get_comments,
    get_current_user_account_id,
    get_issue,
    list_transitions,
    search_issues,
    update_issue_fields,
)
from ticket_impl.storage import map_uuid_to_key

BASE = f"https://api.atlassian.com/ex/jira/{settings.jira_cloud_id}/rest/api/3"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_fallback_to_current_user(seed_token: None) -> None:
    """Test create_ticket falls back to current user when reporter search fails."""
    # Reporter search fails
    respx.get(re.compile(f"{re.escape(BASE)}/user/search\\?.*")).mock(
        return_value=httpx.Response(500, json={"error": "Search failed"}),
    )
    # Current user lookup succeeds
    respx.get(f"{BASE}/myself").mock(
        return_value=httpx.Response(200, json={"accountId": "current-user-id"}),
    )
    # Create succeeds
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}),
    )
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": "OSDP-101",
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Current User"},
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.create_ticket(
        title="Test",
        description="desc",
        reporter="nonexistent@example.com",
    )
    assert ticket.title == "Test"


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_with_exception(seed_token: None) -> None:
    """Test get_ticket raises TicketNotFoundError on exception."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(500, json={"error": "Server error"}))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(TicketNotFoundError):
        await svc.get_ticket(ticket_id)


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_with_filters(seed_token: None) -> None:
    """Test list_tickets with various filter combinations."""
    # Test with status filter
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(
            200,
            json={
                "issues": [
                    {
                        "key": "OSDP-101",
                        "fields": {
                            "summary": "Test",
                            "status": {"name": "In Progress"},
                            "priority": {"name": "Medium"},
                            "description": "desc",
                            "assignee": None,
                            "reporter": {"displayName": "Reporter"},
                        },
                    },
                ],
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    tickets = await svc.list_tickets(status=TicketStatus.IN_PROGRESS)
    assert len(tickets) == 1
    assert tickets[0].status == TicketStatus.IN_PROGRESS

    # Test with assignee filter
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(200, json={"issues": []}),
    )
    tickets = await svc.list_tickets(assignee="user@example.com")
    assert len(tickets) == 0

    # Test with reporter filter
    tickets = await svc.list_tickets(reporter="reporter@example.com")
    assert len(tickets) == 0


@pytest.mark.asyncio
@respx.mock
async def test_update_ticket_without_status(seed_token: None) -> None:
    """Test update_ticket without status change."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.update_ticket(ticket_id)
    assert ticket.status == TicketStatus.OPEN


@pytest.mark.asyncio
@respx.mock
async def test_delete_ticket_success(seed_token: None) -> None:
    """Test successful ticket deletion."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.delete(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(204))

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    result = await svc.delete_ticket(ticket_id)
    assert result is True


@pytest.mark.asyncio
@respx.mock
async def test_add_comment_success(seed_token: None) -> None:
    """Test successful comment addition."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.post(f"{BASE}/issue/{key}/comment").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "comment-1",
                "body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Test comment"}]}]},
                "author": {"displayName": "Author"},
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    comment = await svc.add_comment(ticket_id, "author@example.com", "Test comment")
    assert comment.content == "Test comment"


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_comments_success(seed_token: None) -> None:
    """Test getting ticket comments."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/issue/{key}/comment").mock(
        return_value=httpx.Response(
            200,
            json={
                "comments": [
                    {
                        "id": "comment-1",
                        "body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Comment 1"}]}]},
                        "author": {"displayName": "Author1"},
                    },
                    {
                        "id": "comment-2",
                        "body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Comment 2"}]}]},
                        "author": {"displayName": "Author2"},
                    },
                ],
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    comments = await svc.get_ticket_comments(ticket_id)
    assert len(comments) == 2
    assert comments[0].content == "Comment 1"
    assert comments[1].content == "Comment 2"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_get_issue(seed_token: None) -> None:
    """Test jira_client.get_issue."""
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(
            200,
            json={"id": "10001", "key": "OSDP-101", "fields": {"summary": "Test"}},
        ),
    )

    result = await get_issue("u1", "OSDP-101")
    assert result["key"] == "OSDP-101"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_delete_issue(seed_token: None) -> None:
    """Test jira_client.delete_issue."""
    respx.delete(f"{BASE}/issue/OSDP-101").mock(return_value=httpx.Response(204))

    result = await delete_issue("u1", "OSDP-101")
    assert result is True

    # Test non-204 response
    respx.delete(f"{BASE}/issue/OSDP-102").mock(return_value=httpx.Response(200))
    result = await delete_issue("u1", "OSDP-102")
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_search_issues(seed_token: None) -> None:
    """Test jira_client.search_issues."""
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(
            200,
            json={"issues": [{"key": "OSDP-101", "fields": {"summary": "Test"}}]},
        ),
    )

    result = await search_issues("u1", 'project = "OSDP"', max_results=50, start_at=0)
    assert "issues" in result
    assert len(result["issues"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_create_issue(seed_token: None) -> None:
    """Test jira_client.create_issue."""
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}),
    )

    result = await create_issue(
        "u1",
        "OSDP",
        "Test",
        "Description",
        assignee_account_id="acc-1",
        reporter_account_id="acc-2",
    )
    assert result["key"] == "OSDP-101"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_update_issue_fields(seed_token: None) -> None:
    """Test jira_client.update_issue_fields."""
    # Test with NO_CONTENT response (fetches issue)
    respx.put(f"{BASE}/issue/OSDP-101").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(
            200,
            json={"id": "10001", "key": "OSDP-101", "fields": {"summary": "Updated"}},
        ),
    )

    result = await update_issue_fields("u1", "OSDP-101", {"summary": "Updated"})
    assert result["key"] == "OSDP-101"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_list_transitions(seed_token: None) -> None:
    """Test jira_client.list_transitions."""
    respx.get(f"{BASE}/issue/OSDP-101/transitions").mock(
        return_value=httpx.Response(
            200,
            json={"transitions": [{"id": "1", "name": "In Progress"}, {"id": "2", "name": "Done"}]},
        ),
    )

    result = await list_transitions("u1", "OSDP-101")
    assert len(result) == 2
    assert result[0]["name"] == "In Progress"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_do_transition(seed_token: None) -> None:
    """Test jira_client.do_transition."""
    respx.post(f"{BASE}/issue/OSDP-101/transitions").mock(return_value=httpx.Response(204))

    await do_transition("u1", "OSDP-101", "transition-1")


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_add_comment(seed_token: None) -> None:
    """Test jira_client.add_comment."""
    respx.post(f"{BASE}/issue/OSDP-101/comment").mock(
        return_value=httpx.Response(
            201,
            json={"id": "comment-1", "body": {"type": "doc"}, "author": {"displayName": "Author"}},
        ),
    )

    result = await add_comment("u1", "OSDP-101", "Comment text")
    assert result["id"] == "comment-1"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_get_comments(seed_token: None) -> None:
    """Test jira_client.get_comments."""
    respx.get(f"{BASE}/issue/OSDP-101/comment").mock(
        return_value=httpx.Response(
            200,
            json={"comments": [{"id": "comment-1", "body": {"type": "doc"}, "author": {"displayName": "Author"}}]},
        ),
    )

    result = await get_comments("u1", "OSDP-101")
    assert "comments" in result
    assert len(result["comments"]) == 1


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_get_current_user_account_id(seed_token: None) -> None:
    """Test jira_client.get_current_user_account_id."""
    respx.get(f"{BASE}/myself").mock(
        return_value=httpx.Response(200, json={"accountId": "user-123", "displayName": "User"}),
    )

    result = await get_current_user_account_id("u1")
    assert result == "user-123"

    # Test with None accountId
    respx.get(f"{BASE}/myself").mock(
        return_value=httpx.Response(200, json={"displayName": "User"}),
    )
    result = await get_current_user_account_id("u1")
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_find_user_account_id(seed_token: None) -> None:
    """Test jira_client.find_user_account_id."""
    # Test successful search
    respx.get(f"{BASE}/user/search").mock(
        return_value=httpx.Response(200, json=[{"accountId": "acc-1", "displayName": "User"}]),
    )

    result = await find_user_account_id("u1", "user@example.com")
    assert result == "acc-1"

    # Test empty result
    respx.get(f"{BASE}/user/search").mock(return_value=httpx.Response(200, json=[]))
    result = await find_user_account_id("u1", "nonexistent@example.com")
    assert result is None

    # Test search failure (returns None)
    respx.get(f"{BASE}/user/search").mock(return_value=httpx.Response(500, json={"error": "Server error"}))
    result = await find_user_account_id("u1", "user@example.com")
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_priority_to_jira_all_levels(seed_token: None) -> None:
    """Test _priority_to_jira covers all priority levels."""
    assert _priority_to_jira(TicketPriority.LOW) == "Low"
    assert _priority_to_jira(TicketPriority.MEDIUM) == "Medium"
    assert _priority_to_jira(TicketPriority.HIGH) == "High"
    assert _priority_to_jira(TicketPriority.CRITICAL) == "Highest"


@pytest.mark.asyncio
@respx.mock
async def test_status_name_to_domain_all_variants(seed_token: None) -> None:
    """Test _status_name_to_domain covers all status name variants."""
    assert _status_name_to_domain("Open") == TicketStatus.OPEN
    assert _status_name_to_domain("To Do") == TicketStatus.OPEN
    assert _status_name_to_domain("to-do") == TicketStatus.OPEN
    assert _status_name_to_domain("In Progress") == TicketStatus.IN_PROGRESS
    assert _status_name_to_domain("Doing") == TicketStatus.IN_PROGRESS
    assert _status_name_to_domain("in-progress") == TicketStatus.IN_PROGRESS
    assert _status_name_to_domain("Done") == TicketStatus.RESOLVED
    assert _status_name_to_domain("Resolved") == TicketStatus.RESOLVED
    assert _status_name_to_domain("Closed") == TicketStatus.CLOSED
    assert _status_name_to_domain("closed") == TicketStatus.CLOSED


@pytest.mark.asyncio
@respx.mock
async def test_jira_to_ticket_all_fields(seed_token: None) -> None:
    """Test _jira_to_ticket with all fields present."""
    data = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test Ticket",
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "description": "Test description",
            "assignee": {"displayName": "Assignee"},
            "reporter": {"displayName": "Reporter"},
        },
    }

    ticket = _jira_to_ticket(data, "user1")
    assert ticket.title == "Test Ticket"
    assert ticket.status == TicketStatus.IN_PROGRESS
    assert ticket.priority == TicketPriority.HIGH
    assert ticket.description == "Test description"
    assert ticket.assignee == "Assignee"
    assert ticket.reporter == "Reporter"


@pytest.mark.asyncio
@respx.mock
async def test_adf_paragraph_helper(seed_token: None) -> None:
    """Test _adf_paragraph helper function."""
    result = _adf_paragraph("Test text")
    assert result["type"] == "doc"
    assert result["version"] == 1
    assert "content" in result
    assert result["content"][0]["type"] == "paragraph"
    assert result["content"][0]["content"][0]["text"] == "Test text"


@pytest.mark.asyncio
@respx.mock
async def test_update_ticket_all_status_transitions(seed_token: None) -> None:
    """Test update_ticket with all status transitions."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    statuses = [
        (TicketStatus.OPEN, "Open"),
        (TicketStatus.IN_PROGRESS, "In Progress"),
        (TicketStatus.RESOLVED, "Done"),
        (TicketStatus.CLOSED, "Closed"),
    ]

    for status, transition_name in statuses:
        respx.get(f"{BASE}/issue/{key}/transitions").mock(
            return_value=httpx.Response(
                200,
                json={"transitions": [{"id": "1", "name": transition_name}]},
            ),
        )
        respx.post(f"{BASE}/issue/{key}/transitions").mock(return_value=httpx.Response(204))
        respx.get(f"{BASE}/issue/{key}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "10001",
                    "key": key,
                    "fields": {
                        "summary": "Test",
                        "status": {"name": transition_name},
                        "priority": {"name": "Medium"},
                        "description": "desc",
                        "assignee": None,
                        "reporter": {"displayName": "Reporter"},
                    },
                },
            ),
        )

        svc = TicketImpl(user_id="u1", project_key="OSDP")
        ticket = await svc.update_ticket(ticket_id, status=status)
        assert ticket.status == status


@pytest.mark.asyncio
@respx.mock
async def test_reassign_ticket_success_with_mapping(seed_token: None) -> None:
    """Test reassign_ticket with successful user mapping."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/user/search").mock(
        return_value=httpx.Response(200, json=[{"accountId": "acc-2", "displayName": "NewAssignee"}]),
    )
    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": {"displayName": "NewAssignee"},
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.reassign_ticket(ticket_id, "newassignee@example.com")
    assert ticket.assignee == "NewAssignee"


@pytest.mark.asyncio
@respx.mock
async def test_update_priority_success(seed_token: None) -> None:
    """Test update_priority successfully."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Highest"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.update_priority(ticket_id, TicketPriority.CRITICAL)
    assert ticket.priority == TicketPriority.CRITICAL


@pytest.mark.asyncio
@respx.mock
async def test_update_description_success(seed_token: None) -> None:
    """Test update_description successfully."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Medium"},
                    "description": "Updated description",
                    "assignee": None,
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.update_description(ticket_id, "Updated description")
    assert ticket.description == "Updated description"


@pytest.mark.asyncio
@respx.mock
async def test_jira_to_ticket_edge_cases(seed_token: None) -> None:
    """Test _jira_to_ticket with various edge cases to cover all lines."""
    # Test with missing key
    data_no_key = {
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "priority": {"name": "Medium"},
        },
    }
    ticket = _jira_to_ticket(data_no_key, "user1")
    assert ticket.title == "Test"

    # Test with different priority names
    for priority_name, expected in [
        ("low", TicketPriority.LOW),
        ("LOW", TicketPriority.LOW),
        ("medium", TicketPriority.MEDIUM),
        ("high", TicketPriority.HIGH),
        ("highest", TicketPriority.CRITICAL),
        ("unknown", TicketPriority.MEDIUM),  # default
    ]:
        data = {
            "key": "OSDP-101",
            "fields": {
                "summary": "Test",
                "status": {"name": "Open"},
                "priority": {"name": priority_name},
            },
        }
        ticket = _jira_to_ticket(data, "user1")
        assert ticket.priority == expected

    # Test with dict description (non-string)
    data_dict_desc = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "priority": {"name": "Medium"},
            "description": {"type": "doc", "content": []},
        },
    }
    ticket = _jira_to_ticket(data_dict_desc, "user1")
    assert isinstance(ticket.description, str)


@pytest.mark.asyncio
@respx.mock
async def test_jira_comment_to_domain_comprehensive(seed_token: None) -> None:
    """Test _jira_comment_to_domain with various comment formats."""
    from ticket_impl.impl import _jira_comment_to_domain

    ticket_id = uuid4()

    # Test with full ADF structure
    full_comment = {
        "id": "c-1",
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "First paragraph"},
                        {"type": "text", "text": " continued"},
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second paragraph"}],
                },
            ],
        },
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(full_comment, ticket_id)
    assert "First paragraph" in comment.content
    assert "Second paragraph" in comment.content

    # Test with missing author
    no_author = {
        "id": "c-2",
        "body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Text"}]}]},
    }
    comment = _jira_comment_to_domain(no_author, ticket_id)
    assert comment.author == "unknown"


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_comprehensive(seed_token: None) -> None:
    """Test list_tickets covers all code paths including logger calls."""
    # Test with multiple issues returned
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(
            200,
            json={
                "issues": [
                    {
                        "key": "OSDP-101",
                        "fields": {
                            "summary": "Ticket 1",
                            "status": {"name": "Open"},
                            "priority": {"name": "Medium"},
                            "description": "desc1",
                            "assignee": None,
                            "reporter": {"displayName": "Reporter1"},
                        },
                    },
                    {
                        "key": "OSDP-102",
                        "fields": {
                            "summary": "Ticket 2",
                            "status": {"name": "In Progress"},
                            "priority": {"name": "High"},
                            "description": "desc2",
                            "assignee": {"displayName": "Assignee"},
                            "reporter": {"displayName": "Reporter2"},
                        },
                    },
                ],
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    tickets = await svc.list_tickets()
    assert len(tickets) == 2
    assert tickets[0].title == "Ticket 1"
    assert tickets[1].title == "Ticket 2"

    # Test with empty issues list
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(200, json={"issues": []}),
    )
    tickets = await svc.list_tickets(status=TicketStatus.RESOLVED, assignee="user@example.com", reporter="reporter@example.com")
    assert len(tickets) == 0

    # Test with limit and offset
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(200, json={"issues": []}),
    )
    tickets = await svc.list_tickets(limit=10, offset=5)
    assert len(tickets) == 0


@pytest.mark.asyncio
@respx.mock
async def test_update_ticket_transition_all_paths(seed_token: None) -> None:
    """Test update_ticket covers all transition paths."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    # Test with "To Do" transition name
    respx.get(f"{BASE}/issue/{key}/transitions").mock(
        return_value=httpx.Response(
            200,
            json={"transitions": [{"id": "1", "name": "To Do"}]},
        ),
    )
    respx.post(f"{BASE}/issue/{key}/transitions").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "To Do"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.update_ticket(ticket_id, status=TicketStatus.OPEN)
    assert ticket.status == TicketStatus.OPEN

    # Test with "Doing" transition name
    respx.get(f"{BASE}/issue/{key}/transitions").mock(
        return_value=httpx.Response(
            200,
            json={"transitions": [{"id": "1", "name": "Doing"}]},
        ),
    )
    respx.post(f"{BASE}/issue/{key}/transitions").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Doing"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )
    ticket = await svc.update_ticket(ticket_id, status=TicketStatus.IN_PROGRESS)
    assert ticket.status == TicketStatus.IN_PROGRESS

    # Test with "Resolved" transition name
    respx.get(f"{BASE}/issue/{key}/transitions").mock(
        return_value=httpx.Response(
            200,
            json={"transitions": [{"id": "1", "name": "Resolved"}]},
        ),
    )
    respx.post(f"{BASE}/issue/{key}/transitions").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": key,
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Resolved"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )
    ticket = await svc.update_ticket(ticket_id, status=TicketStatus.RESOLVED)
    assert ticket.status == TicketStatus.RESOLVED


@pytest.mark.asyncio
@respx.mock
async def test_reassign_ticket_exception_handling(seed_token: None) -> None:
    """Test reassign_ticket exception handling paths."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    # Test with TicketNotFoundError (should be re-raised)
    respx.get(f"{BASE}/user/search").mock(
        return_value=httpx.Response(200, json=[{"accountId": "acc-2", "displayName": "NewAssignee"}]),
    )
    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(404))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError):
        await svc.reassign_ticket(ticket_id, "newassignee@example.com")


@pytest.mark.asyncio
@respx.mock
async def test_update_priority_exception_handling(seed_token: None) -> None:
    """Test update_priority exception handling paths."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    # Test with exception (should be caught and re-raised as ServiceError)
    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(404))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="Failed to update priority"):
        await svc.update_priority(ticket_id, TicketPriority.HIGH)


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_headers_and_adf(seed_token: None) -> None:
    """Test jira_client helper functions are called."""
    from ticket_impl.jira_client import _v3

    # Test _v3 helper
    path = _v3("/issue/OSDP-101")
    assert path.endswith("/rest/api/3/issue/OSDP-101")

    # Test _adf_paragraph is used (covered by create_issue)
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}),
    )
    result = await create_issue("u1", "OSDP", "Test", "Description with ADF", assignee_account_id=None, reporter_account_id=None)
    assert result["key"] == "OSDP-101"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_update_issue_fields_with_content(seed_token: None) -> None:
    """Test update_issue_fields with content in response."""
    respx.put(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(
            200,
            json={"id": "10001", "key": "OSDP-101", "fields": {"summary": "Updated"}},
        ),
    )

    result = await update_issue_fields("u1", "OSDP-101", {"summary": "Updated"})
    assert result["key"] == "OSDP-101"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_search_issues_error_handling(seed_token: None) -> None:
    """Test search_issues error handling."""
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(400, json={"error": "Invalid JQL"}),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await search_issues("u1", "invalid jql", max_results=50, start_at=0)


# Direct tests for helper functions to ensure full coverage
def test_priority_to_jira_direct() -> None:
    """Test _priority_to_jira directly to ensure all branches are covered."""
    assert _priority_to_jira(TicketPriority.LOW) == "Low"
    assert _priority_to_jira(TicketPriority.MEDIUM) == "Medium"
    assert _priority_to_jira(TicketPriority.HIGH) == "High"
    assert _priority_to_jira(TicketPriority.CRITICAL) == "Highest"


def test_status_name_to_domain_direct() -> None:
    """Test _status_name_to_domain directly to ensure all branches are covered."""
    # Test None/empty
    assert _status_name_to_domain(None) == TicketStatus.OPEN
    assert _status_name_to_domain("") == TicketStatus.OPEN
    
    # Test all variants
    assert _status_name_to_domain("Open") == TicketStatus.OPEN
    assert _status_name_to_domain("To Do") == TicketStatus.OPEN
    assert _status_name_to_domain("to-do") == TicketStatus.OPEN
    assert _status_name_to_domain("to_do") == TicketStatus.OPEN
    assert _status_name_to_domain("TO DO") == TicketStatus.OPEN
    
    assert _status_name_to_domain("In Progress") == TicketStatus.IN_PROGRESS
    assert _status_name_to_domain("Doing") == TicketStatus.IN_PROGRESS
    assert _status_name_to_domain("in-progress") == TicketStatus.IN_PROGRESS
    assert _status_name_to_domain("in_progress") == TicketStatus.IN_PROGRESS
    
    assert _status_name_to_domain("Done") == TicketStatus.RESOLVED
    assert _status_name_to_domain("Resolved") == TicketStatus.RESOLVED
    assert _status_name_to_domain("done") == TicketStatus.RESOLVED
    
    assert _status_name_to_domain("Closed") == TicketStatus.CLOSED
    assert _status_name_to_domain("closed") == TicketStatus.CLOSED
    
    # Test unknown status (defaults to OPEN)
    assert _status_name_to_domain("Unknown") == TicketStatus.OPEN
    assert _status_name_to_domain("Random Status") == TicketStatus.OPEN


def test_jira_to_ticket_direct() -> None:
    """Test _jira_to_ticket directly to ensure all code paths are covered."""
    # Test with all fields
    data_full = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test Ticket",
            "status": {"name": "In Progress"},
            "priority": {"name": "High"},
            "description": "Test description",
            "assignee": {"displayName": "Assignee"},
            "reporter": {"displayName": "Reporter"},
        },
    }
    ticket = _jira_to_ticket(data_full, "user1")
    assert ticket.title == "Test Ticket"
    assert ticket.status == TicketStatus.IN_PROGRESS
    assert ticket.priority == TicketPriority.HIGH
    assert ticket.description == "Test description"
    assert ticket.assignee == "Assignee"
    assert ticket.reporter == "Reporter"
    
    # Test with missing key
    data_no_key = {
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "priority": {"name": "Medium"},
        },
    }
    ticket = _jira_to_ticket(data_no_key, "user1")
    assert ticket.title == "Test"
    
    # Test with missing fields
    data_minimal = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            # Missing status, priority, description, assignee, reporter
        },
    }
    ticket = _jira_to_ticket(data_minimal, "user1")
    assert ticket.title == "Test"
    assert ticket.status == TicketStatus.OPEN  # Default
    assert ticket.priority == TicketPriority.MEDIUM  # Default
    assert ticket.description == ""  # Default
    assert ticket.assignee is None
    assert ticket.reporter == ""  # Default
    
    # Test with None status
    data_none_status = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            "status": None,
            "priority": {"name": "Medium"},
        },
    }
    ticket = _jira_to_ticket(data_none_status, "user1")
    assert ticket.status == TicketStatus.OPEN
    
    # Test with dict description (non-string)
    data_dict_desc = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "priority": {"name": "Medium"},
            "description": {"type": "doc", "content": []},
        },
    }
    ticket = _jira_to_ticket(data_dict_desc, "user1")
    assert isinstance(ticket.description, str)
    
    # Test with None description
    data_none_desc = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "priority": {"name": "Medium"},
            "description": None,
        },
    }
    ticket = _jira_to_ticket(data_none_desc, "user1")
    assert ticket.description == ""
    
    # Test priority mapping
    for priority_name, expected in [
        ("low", TicketPriority.LOW),
        ("LOW", TicketPriority.LOW),
        ("medium", TicketPriority.MEDIUM),
        ("MEDIUM", TicketPriority.MEDIUM),
        ("high", TicketPriority.HIGH),
        ("HIGH", TicketPriority.HIGH),
        ("highest", TicketPriority.CRITICAL),
        ("HIGHEST", TicketPriority.CRITICAL),
        ("unknown", TicketPriority.MEDIUM),  # default
    ]:
        data = {
            "key": "OSDP-101",
            "fields": {
                "summary": "Test",
                "status": {"name": "Open"},
                "priority": {"name": priority_name},
            },
        }
        ticket = _jira_to_ticket(data, "user1")
        assert ticket.priority == expected
    
    # Test with None assignee and reporter
    data_none_people = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "priority": {"name": "Medium"},
            "assignee": None,
            "reporter": None,
        },
    }
    ticket = _jira_to_ticket(data_none_people, "user1")
    assert ticket.assignee is None
    assert ticket.reporter == ""


def test_jira_comment_to_domain_direct() -> None:
    """Test _jira_comment_to_domain directly to ensure all code paths are covered."""
    from ticket_impl.impl import _jira_comment_to_domain
    
    ticket_id = uuid4()
    
    # Test with full ADF structure
    full_comment = {
        "id": "c-1",
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "First"},
                        {"type": "text", "text": " paragraph"},
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second paragraph"}],
                },
                {
                    "type": "other",  # Non-paragraph block
                    "content": [{"type": "text", "text": "Ignored"}],
                },
            ],
        },
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(full_comment, ticket_id)
    assert "First paragraph" in comment.content
    assert "Second paragraph" in comment.content
    
    # Test with empty body
    empty_comment = {
        "id": "c-2",
        "body": {},
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(empty_comment, ticket_id)
    assert comment.content == "<empty>"
    
    # Test with missing body
    no_body_comment = {
        "id": "c-3",
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(no_body_comment, ticket_id)
    assert comment.content == "<empty>"
    
    # Test with body but no content
    no_content_comment = {
        "id": "c-4",
        "body": {"type": "doc", "version": 1},
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(no_content_comment, ticket_id)
    assert comment.content == "<empty>"
    
    # Test with empty content array
    empty_content_comment = {
        "id": "c-5",
        "body": {"type": "doc", "version": 1, "content": []},
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(empty_content_comment, ticket_id)
    assert comment.content == "<empty>"
    
    # Test with paragraph but no text nodes
    no_text_comment = {
        "id": "c-6",
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": []}],
        },
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(no_text_comment, ticket_id)
    assert comment.content == "<empty>"
    
    # Test with missing author
    no_author_comment = {
        "id": "c-7",
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Text"}]}],
        },
    }
    comment = _jira_comment_to_domain(no_author_comment, ticket_id)
    assert comment.author == "unknown"
    
    # Test with None author
    none_author_comment = {
        "id": "c-8",
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Text"}]}],
        },
        "author": None,
    }
    comment = _jira_comment_to_domain(none_author_comment, ticket_id)
    assert comment.author == "unknown"
    
    # Test with author but no displayName
    no_display_name_comment = {
        "id": "c-9",
        "body": {
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Text"}]}],
        },
        "author": {},
    }
    comment = _jira_comment_to_domain(no_display_name_comment, ticket_id)
    assert comment.author == "unknown"
    
    # Test with non-dict body (should handle gracefully)
    non_dict_body = {
        "id": "c-10",
        "body": "plain text",
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(non_dict_body, ticket_id)
    assert comment.content == "<empty>"


def test_adf_paragraph_direct() -> None:
    """Test _adf_paragraph directly."""
    result = _adf_paragraph("Test text")
    assert result["type"] == "doc"
    assert result["version"] == 1
    assert "content" in result
    assert len(result["content"]) == 1
    assert result["content"][0]["type"] == "paragraph"
    assert len(result["content"][0]["content"]) == 1
    assert result["content"][0]["content"][0]["type"] == "text"
    assert result["content"][0]["content"][0]["text"] == "Test text"
    
    # Test with empty string
    result = _adf_paragraph("")
    assert result["content"][0]["content"][0]["text"] == ""
    
    # Test with special characters
    result = _adf_paragraph("Text with\nnewlines\tand\ttabs")
    assert "newlines" in result["content"][0]["content"][0]["text"]


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_fallback_to_current_user_comprehensive(seed_token: None) -> None:
    """Test create_ticket fallback to current user when reporter search fails - comprehensive."""
    # Reporter search fails (returns empty or error)
    respx.get(re.compile(f"{re.escape(BASE)}/user/search\\?.*")).mock(
        return_value=httpx.Response(500, json={"error": "Search failed"}),
    )
    # Current user lookup succeeds
    respx.get(f"{BASE}/myself").mock(
        return_value=httpx.Response(200, json={"accountId": "current-user-id", "displayName": "Current User"}),
    )
    # Create succeeds
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}),
    )
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": "OSDP-101",
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Current User"},
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.create_ticket(
        title="Test",
        description="desc",
        reporter="nonexistent@example.com",
    )
    assert ticket.title == "Test"
    assert ticket.reporter == "Current User"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_fallback_empty_search_result(seed_token: None) -> None:
    """Test create_ticket fallback when user search returns empty."""
    # Reporter search returns empty
    respx.get(re.compile(f"{re.escape(BASE)}/user/search\\?.*")).mock(
        return_value=httpx.Response(200, json=[]),
    )
    # Current user lookup succeeds
    respx.get(f"{BASE}/myself").mock(
        return_value=httpx.Response(200, json={"accountId": "current-user-id"}),
    )
    # Create succeeds
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}),
    )
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": "OSDP-101",
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": None,
                },
            },
        ),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.create_ticket(
        title="Test",
        description="desc",
        reporter="nonexistent@example.com",
    )
    assert ticket.title == "Test"



# Additional comprehensive tests for jira_client functions
@pytest.mark.asyncio
@respx.mock
async def test_jira_client_get_issue_comprehensive(seed_token: None) -> None:
    """Test get_issue covers all code paths."""
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(
            200,
            json={"id": "10001", "key": "OSDP-101", "fields": {"summary": "Test"}},
        ),
    )
    result = await get_issue("u1", "OSDP-101")
    assert result["key"] == "OSDP-101"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_delete_issue_all_paths(seed_token: None) -> None:
    """Test delete_issue covers all code paths."""
    respx.delete(f"{BASE}/issue/OSDP-101").mock(return_value=httpx.Response(204))
    result = await delete_issue("u1", "OSDP-101")
    assert result is True
    respx.delete(f"{BASE}/issue/OSDP-102").mock(return_value=httpx.Response(200))
    result = await delete_issue("u1", "OSDP-102")
    assert result is False


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_search_issues_all_paths(seed_token: None) -> None:
    """Test search_issues covers all code paths including error logging."""
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(
            200,
            json={"issues": [{"key": "OSDP-101", "fields": {"summary": "Test"}}]},
        ),
    )
    result = await search_issues("u1", 'project = "OSDP"', max_results=50, start_at=0)
    assert "issues" in result
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(400, json={"error": "Invalid JQL"}),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await search_issues("u1", "invalid", max_results=50, start_at=0)


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_create_issue_all_paths(seed_token: None) -> None:
    """Test create_issue covers all code paths including error logging."""
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}),
    )
    result = await create_issue("u1", "OSDP", "Test", "Description", assignee_account_id="acc-1", reporter_account_id="acc-2")
    assert result["key"] == "OSDP-101"
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10002", "key": "OSDP-102"}),
    )
    result = await create_issue("u1", "OSDP", "Test", None, assignee_account_id=None, reporter_account_id=None)
    assert result["key"] == "OSDP-102"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_update_issue_fields_all_paths(seed_token: None) -> None:
    """Test update_issue_fields covers all code paths."""
    respx.put(f"{BASE}/issue/OSDP-101").mock(return_value=httpx.Response(204))
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(200, json={"id": "10001", "key": "OSDP-101", "fields": {"summary": "Updated"}}),
    )
    result = await update_issue_fields("u1", "OSDP-101", {"summary": "Updated"})
    assert result["key"] == "OSDP-101"
    respx.put(f"{BASE}/issue/OSDP-102").mock(return_value=httpx.Response(200, content=b""))
    respx.get(f"{BASE}/issue/OSDP-102").mock(
        return_value=httpx.Response(200, json={"id": "10002", "key": "OSDP-102", "fields": {"summary": "Updated2"}}),
    )
    result = await update_issue_fields("u1", "OSDP-102", {"summary": "Updated2"})
    assert result["key"] == "OSDP-102"


@pytest.mark.asyncio
@respx.mock
async def test_jira_client_list_transitions_comprehensive(seed_token: None) -> None:
    """Test list_transitions covers all code paths."""
    respx.get(f"{BASE}/issue/OSDP-101/transitions").mock(
        return_value=httpx.Response(
            200,
            json={"transitions": [{"id": "1", "name": "In Progress"}, {"id": "2", "name": "Done"}]},
        ),
    )
    result = await list_transitions("u1", "OSDP-101")
    assert len(result) == 2
    respx.get(f"{BASE}/issue/OSDP-102/transitions").mock(
        return_value=httpx.Response(200, json={"transitions": []}),
    )
    result = await list_transitions("u1", "OSDP-102")
    assert len(result) == 0
    respx.get(f"{BASE}/issue/OSDP-103/transitions").mock(
        return_value=httpx.Response(200, json={}),
    )
    result = await list_transitions("u1", "OSDP-103")
    assert len(result) == 0


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_with_all_filters_combined(seed_token: None) -> None:
    """Test list_tickets with all filters combined to cover all code paths."""
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(
            200,
            json={
                "issues": [
                    {
                        "key": "OSDP-101",
                        "fields": {
                            "summary": "Test",
                            "status": {"name": "In Progress"},
                            "priority": {"name": "High"},
                            "description": "desc",
                            "assignee": {"displayName": "Assignee"},
                            "reporter": {"displayName": "Reporter"},
                        },
                    },
                ],
            },
        ),
    )
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    tickets = await svc.list_tickets(
        status=TicketStatus.IN_PROGRESS,
        assignee="assignee@example.com",
        reporter="reporter@example.com",
        limit=10,
        offset=0,
    )
    assert len(tickets) == 1


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_with_str_ticket_id(seed_token: None) -> None:
    """Test get_ticket when UUID mapping doesn't exist (uses str(ticket_id))."""
    ticket_id = uuid4()
    respx.get(f"{BASE}/issue/{ticket_id}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "10001",
                "key": str(ticket_id),
                "fields": {
                    "summary": "Test",
                    "status": {"name": "Open"},
                    "priority": {"name": "Medium"},
                    "description": "desc",
                    "assignee": None,
                    "reporter": {"displayName": "Reporter"},
                },
            },
        ),
    )
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket = await svc.get_ticket(ticket_id)
    assert ticket.title == "Test"
