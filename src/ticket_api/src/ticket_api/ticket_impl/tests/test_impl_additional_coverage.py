"""Additional tests to cover remaining lines in impl.py to reach 85%+ coverage."""

import re
from uuid import uuid4

import httpx
import pytest
import respx
from ticket_api.ticket_impl.exceptions import ServiceError
from ticket_api.ticket_impl.models import TicketStatus
from ticket_impl import TicketImpl
from ticket_impl.config import settings
from ticket_impl.storage import map_uuid_to_key

BASE = f"https://api.atlassian.com/ex/jira/{settings.jira_cloud_id}/rest/api/3"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_priority_medium_no_update(seed_token: None) -> None:
    """Test create_ticket with MEDIUM priority (line 153: no priority update)."""
    respx.get(f"{BASE}/user/search").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE}/myself").mock(return_value=httpx.Response(200, json={"accountId": "current-user-id"}))
    respx.post(f"{BASE}/issue").mock(return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}))
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
    # Use MEDIUM priority - should skip the priority update (line 153)
    from ticket_api.ticket_impl.models import TicketPriority
    ticket = await svc.create_ticket(
        title="Test",
        description="desc",
        reporter="test@example.com",
        priority=TicketPriority.MEDIUM,
    )
    assert ticket.priority == TicketPriority.MEDIUM


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_negative_limit(seed_token: None) -> None:
    """Test list_tickets with negative limit (line 182: ValueError)."""
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(ValueError, match="limit/offset must be non-negative"):
        await svc.list_tickets(limit=-1)


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_negative_offset(seed_token: None) -> None:
    """Test list_tickets with negative offset (line 182: ValueError)."""
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(ValueError, match="limit/offset must be non-negative"):
        await svc.list_tickets(offset=-1)


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_exception_handling(seed_token: None) -> None:
    """Test list_tickets exception handling (line 203-205: ServiceError)."""
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    respx.post(f"{BASE}/search/jql").mock(return_value=httpx.Response(500))
    with pytest.raises(ServiceError, match="Failed to list tickets"):
        await svc.list_tickets()


@pytest.mark.asyncio
@respx.mock
async def test_transition_status_no_valid_transition(seed_token: None) -> None:
    """Test transition_status when no valid transition found (line 243-244: ServiceError)."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.get(f"{BASE}/issue/{key}/transitions").mock(
        return_value=httpx.Response(200, json={"transitions": [{"id": "1", "name": "Wrong Transition"}]}),
    )
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(ServiceError, match="No valid transition found"):
        await svc.transition_status(ticket_id, TicketStatus.CLOSED)


@pytest.mark.asyncio
@respx.mock
async def test_transition_status_exception_handling(seed_token: None) -> None:
    """Test transition_status exception handling (line 250-252: ServiceError)."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.get(f"{BASE}/issue/{key}/transitions").mock(return_value=httpx.Response(500))
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(ServiceError, match="Failed to transition status"):
        await svc.transition_status(ticket_id, TicketStatus.IN_PROGRESS)


@pytest.mark.asyncio
@respx.mock
async def test_reassign_ticket_exception_handling(seed_token: None) -> None:
    """Test reassign_ticket exception handling (line 260-261: ServiceError)."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.get(f"{BASE}/user/search").mock(return_value=httpx.Response(500))
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(ServiceError, match="Failed to reassign ticket"):
        await svc.reassign_ticket(ticket_id, "new@example.com")


@pytest.mark.asyncio
@respx.mock
async def test_update_priority_exception_handling(seed_token: None) -> None:
    """Test update_priority exception handling (line 266: ServiceError)."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(500))
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    from ticket_api.ticket_impl.models import TicketPriority
    with pytest.raises(ServiceError, match="Failed to update priority"):
        await svc.update_priority(ticket_id, TicketPriority.HIGH)


@pytest.mark.asyncio
@respx.mock
async def test_update_description_exception_handling(seed_token: None) -> None:
    """Test update_description exception handling (line 290-291: TicketNotFoundError)."""
    from ticket_api.ticket_impl.exceptions import TicketNotFoundError
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(404))
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(TicketNotFoundError):
        await svc.update_description(ticket_id, "New description")


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_comments_exception_handling(seed_token: None) -> None:
    """Test get_ticket_comments exception handling - no exception handling in this method."""
    # get_ticket_comments doesn't have exception handling, it just calls jc.get_comments
    # So we just need to test it works normally
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.get(f"{BASE}/issue/{key}/comment").mock(
        return_value=httpx.Response(200, json={"comments": []}),
    )
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    comments = await svc.get_ticket_comments(ticket_id)
    assert comments == []


@pytest.mark.asyncio
@respx.mock
async def test_add_comment_exception_handling(seed_token: None) -> None:
    """Test add_comment exception handling (line 315-316: TicketNotFoundError)."""
    from ticket_api.ticket_impl.exceptions import TicketNotFoundError
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.post(f"{BASE}/issue/{key}/comment").mock(return_value=httpx.Response(404))
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(TicketNotFoundError):
        await svc.add_comment(ticket_id, "author@example.com", "Comment text")


@pytest.mark.asyncio
@respx.mock
async def test_delete_ticket_exception_handling(seed_token: None) -> None:
    """Test delete_ticket exception handling (line 315-316: ServiceError)."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    respx.delete(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(500))
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(ServiceError, match="Failed to delete ticket"):
        await svc.delete_ticket(ticket_id)


@pytest.mark.asyncio
@respx.mock
async def test_update_ticket_exception_handling(seed_token: None) -> None:
    """Test update_ticket exception handling (line 250-252: ServiceError)."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)
    # Test exception when getting transitions fails
    respx.get(f"{BASE}/issue/{key}/transitions").mock(return_value=httpx.Response(500))
    svc = TicketImpl(user_id="u1", project_key="OSDP")
    with pytest.raises(ServiceError, match="Failed to transition status"):
        await svc.update_ticket(ticket_id, status=TicketStatus.IN_PROGRESS)


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_logger_lines(seed_token: None) -> None:
    """Test list_tickets to cover logger.debug and logger.info lines (202, 209)."""
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(
            200,
            json={
                "issues": [
                    {
                        "key": "OSDP-101",
                        "fields": {
                            "summary": "Test",
                            "status": {"name": "Open"},
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
    tickets = await svc.list_tickets()
    assert len(tickets) == 1
    assert tickets[0].title == "Test"


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_fallback_logger(seed_token: None) -> None:
    """Test create_ticket fallback to cover logger.info line (138)."""
    # Reporter search fails
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


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_with_assignee_and_reporter_filters(seed_token: None) -> None:
    """Test list_tickets with assignee and reporter filters to cover more code paths."""
    respx.post(f"{BASE}/search/jql").mock(
        return_value=httpx.Response(
            200,
            json={
                "issues": [
                    {
                        "key": "OSDP-101",
                        "fields": {
                            "summary": "Test",
                            "status": {"name": "Open"},
                            "priority": {"name": "Medium"},
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
    tickets = await svc.list_tickets(assignee="assignee@example.com", reporter="reporter@example.com")
    assert len(tickets) == 1


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_with_status_filter(seed_token: None) -> None:
    """Test list_tickets with status filter to cover more code paths."""
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
    tickets = await svc.list_tickets(status=TicketStatus.IN_PROGRESS)
    assert len(tickets) == 1
    assert tickets[0].status == TicketStatus.IN_PROGRESS

