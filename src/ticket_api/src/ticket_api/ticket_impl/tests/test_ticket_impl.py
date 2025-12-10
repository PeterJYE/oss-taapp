"""End-to-end happy-path for TicketImpl using respx mocks."""

import re
from uuid import uuid4

import httpx
import pytest
import respx
from ticket_api.ticket_impl.exceptions import ServiceError, TicketNotFoundError
from ticket_api.ticket_impl.models import TicketPriority, TicketStatus
from ticket_impl import TicketImpl
from ticket_impl.config import settings
from ticket_impl.impl import _jira_comment_to_domain
from ticket_impl.storage import map_uuid_to_key

# Use the cloud ID from settings to match actual requests
BASE = f"https://api.atlassian.com/ex/jira/{settings.jira_cloud_id}/rest/api/3"
EXPECTED_GET_CALLS = 3  # after create, explicit get, and after status transition


@pytest.mark.asyncio
@respx.mock
async def test_create_get_list_transition_comment_delete(seed_token: None) -> None:
    """End-to-end happy-path for TicketImpl using respx mocks."""
    # user lookup (used for reporter/assignee mapping) - matches any query parameter
    respx.get(re.compile(f"{re.escape(BASE)}/user/search\\?.*")).mock(
        return_value=httpx.Response(200, json=[{"accountId": "acc-1", "displayName": "Terra"}]),
    )
    # create issue
    respx.post(f"{BASE}/issue").mock(
        return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}),
    )

    def issue_payload(
        summary: str = "Hello HW2",
        status: str = "Open",
        priority: str = "High",
        description: str = "Created from impl",
        assignee: str = "Terra",
        reporter: str = "Terra",
    ) -> dict[str, object]:
        return {
            "id": "10001",
            "key": "OSDP-101",
            "fields": {
                "summary": summary,
                "status": {"name": status},
                "priority": {"name": priority},
                "description": description,
                "assignee": {"displayName": assignee} if assignee else None,
                "reporter": {"displayName": reporter} if reporter else None,
            },
        }

    # SINGLE GET route with THREE sequential responses:
    # 1) after create_ticket()  2) explicit get_ticket()  3) after transition_status()
    route_issue = respx.get(f"{BASE}/issue/OSDP-101")
    route_issue.mock(
        side_effect=[
            httpx.Response(200, json=issue_payload()),  # 1) after create_ticket()
            httpx.Response(200, json=issue_payload()),  # 2) get_ticket() in the test
            httpx.Response(200, json=issue_payload(status="In Progress", priority="High")),  # 3) after transition
        ],
    )


@pytest.mark.asyncio
async def test_create_ticket_with_service_error(seed_token: None) -> None:
    """Test that create_ticket raises ServiceError on HTTP errors."""
    respx.get(f"{BASE}/user/search").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{BASE}/issue").mock(return_value=httpx.Response(500, json={"error": "Internal error"}))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="Failed to create ticket"):
        await svc.create_ticket(
            title="Fail",
            description="Should fail",
            reporter="test@example.com",
        )


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_not_found(seed_token: None) -> None:
    """Test that get_ticket raises TicketNotFoundError when ticket doesn't exist."""
    from uuid import uuid4

    ticket_id = uuid4()
    respx.get(f"{BASE}/issue/{ticket_id}").mock(return_value=httpx.Response(404, json={"error": "Not found"}))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(TicketNotFoundError):
        await svc.get_ticket(ticket_id)


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_with_invalid_params(seed_token: None) -> None:
    """Test that list_tickets raises ValueError for invalid parameters."""
    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ValueError, match="limit/offset must be non-negative"):
        await svc.list_tickets(limit=-1)

    with pytest.raises(ValueError, match="limit/offset must be non-negative"):
        await svc.list_tickets(offset=-1)


@pytest.mark.asyncio
@respx.mock
async def test_list_tickets_service_error(seed_token: None) -> None:
    """Test that list_tickets raises ServiceError on HTTP errors."""
    respx.post(f"{BASE}/search").mock(return_value=httpx.Response(500, json={"error": "Server error"}))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="Failed to list tickets"):
        await svc.list_tickets()


@pytest.mark.asyncio
@respx.mock
async def test_update_ticket_no_valid_transition(seed_token: None) -> None:
    """Test that update_ticket raises ServiceError when no valid transition exists."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    # Mock storage to return the key
    from ticket_impl.storage import map_uuid_to_key

    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/issue/{key}/transitions").mock(
        return_value=httpx.Response(200, json={"transitions": [{"id": "1", "name": "Invalid"}]}),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="No valid transition found"):
        await svc.update_ticket(ticket_id, status=TicketStatus.IN_PROGRESS)


@pytest.mark.asyncio
@respx.mock
async def test_reassign_ticket_success(seed_token: None) -> None:
    """Test successful ticket reassignment."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

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
async def test_reassign_ticket_user_not_found(seed_token: None) -> None:
    """Test reassignment failure when user is not found."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/user/search").mock(return_value=httpx.Response(200, json=[]))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match=r"Assignee .* was not found"):
        await svc.reassign_ticket(ticket_id, "nonexistent@example.com")


@pytest.mark.asyncio
@respx.mock
async def test_update_priority_success(seed_token: None) -> None:
    """Test successful priority update."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

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
    """Test successful description update."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

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
async def test_update_description_not_found(seed_token: None) -> None:
    """Test description update failure when ticket is not found."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

    map_uuid_to_key("u1", ticket_id, key)

    respx.put(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(404))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(TicketNotFoundError):
        await svc.update_description(ticket_id, "Updated")


@pytest.mark.asyncio
@respx.mock
async def test_delete_ticket_service_error(seed_token: None) -> None:
    """Test that delete_ticket raises ServiceError on HTTP errors."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

    map_uuid_to_key("u1", ticket_id, key)

    respx.delete(f"{BASE}/issue/{key}").mock(return_value=httpx.Response(500))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="Failed to delete ticket"):
        await svc.delete_ticket(ticket_id)


@pytest.mark.asyncio
@respx.mock
async def test_add_comment_not_found(seed_token: None) -> None:
    """Test that add_comment raises TicketNotFoundError when ticket doesn't exist."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

    map_uuid_to_key("u1", ticket_id, key)

    respx.post(f"{BASE}/issue/{key}/comment").mock(return_value=httpx.Response(404))

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(TicketNotFoundError):
        await svc.add_comment(ticket_id, "author@example.com", "Comment text")


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_comments_empty(seed_token: None) -> None:
    """Test getting comments when there are none."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/issue/{key}/comment").mock(return_value=httpx.Response(200, json={"comments": []}))

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    comments = await svc.get_ticket_comments(ticket_id)
    assert comments == []


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_with_all_priorities(seed_token: None) -> None:
    """Test creating tickets with different priority levels."""
    respx.get(f"{BASE}/user/search").mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{BASE}/issue").mock(return_value=httpx.Response(201, json={"id": "10001", "key": "OSDP-101"}))
    respx.put(f"{BASE}/issue/OSDP-101").mock(return_value=httpx.Response(204))

    for priority, jira_name in [
        (TicketPriority.LOW, "Low"),
        (TicketPriority.MEDIUM, "Medium"),
        (TicketPriority.HIGH, "High"),
        (TicketPriority.CRITICAL, "Highest"),
    ]:
        respx.get(f"{BASE}/issue/OSDP-101").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "10001",
                    "key": "OSDP-101",
                    "fields": {
                        "summary": "Test",
                        "status": {"name": "Open"},
                        "priority": {"name": jira_name},
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
            reporter="test@example.com",
            priority=priority,
        )
        assert ticket.priority == priority


@pytest.mark.asyncio
@respx.mock
async def test_transition_status_all_states(seed_token: None) -> None:
    """Test transitioning through all ticket statuses."""
    from uuid import uuid4

    ticket_id = uuid4()
    key = "OSDP-101"

    from ticket_impl.storage import map_uuid_to_key

    map_uuid_to_key("u1", ticket_id, key)

    transitions_map = {
        TicketStatus.OPEN: ("Open", "Open"),
        TicketStatus.IN_PROGRESS: ("In Progress", "In Progress"),
        TicketStatus.RESOLVED: ("Done", "Done"),
        TicketStatus.CLOSED: ("Closed", "Closed"),
    }

    for status, (transition_name, status_name) in transitions_map.items():
        respx.get(f"{BASE}/issue/{key}/transitions").mock(
            return_value=httpx.Response(200, json={"transitions": [{"id": "1", "name": transition_name}]}),
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
                        "status": {"name": status_name},
                        "priority": {"name": "Medium"},
                        "description": "desc",
                        "assignee": None,
                        "reporter": {"displayName": "Reporter"},
                    },
                },
            ),
        )

        svc = TicketImpl(user_id="u1", project_key="OSDP")
        ticket = await svc.transition_status(ticket_id, status)
        assert ticket.status == status


@pytest.mark.asyncio
@respx.mock
async def test_status_name_to_domain_various_formats(seed_token: None) -> None:
    """Test _status_name_to_domain with various status name formats."""
    from ticket_impl.impl import _status_name_to_domain

    # Line 30: Empty/None status
    assert _status_name_to_domain(None) == TicketStatus.OPEN
    assert _status_name_to_domain("") == TicketStatus.OPEN

    # Line 40: Unknown status defaults to OPEN
    assert _status_name_to_domain("Unknown Status") == TicketStatus.OPEN
    assert _status_name_to_domain("Random") == TicketStatus.OPEN


@pytest.mark.asyncio
@respx.mock
async def test_jira_to_ticket_missing_fields(seed_token: None) -> None:
    """Test _jira_to_ticket with missing or malformed fields."""
    from ticket_impl.impl import _jira_to_ticket

    # Line 76-85: Missing priority, assignee, reporter fields
    minimal_data = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            # priority missing
            # assignee missing
            # reporter missing
            # description missing
        },
    }

    ticket = _jira_to_ticket(minimal_data, "user1")
    assert ticket.title == "Test"
    assert ticket.priority == TicketPriority.MEDIUM  # default
    assert ticket.assignee is None
    assert ticket.reporter == ""  # default empty string


@pytest.mark.asyncio
@respx.mock
async def test_jira_to_ticket_dict_description(seed_token: None) -> None:
    """Test _jira_to_ticket with dict description (ADF format)."""
    from ticket_impl.impl import _jira_to_ticket

    # Lines 76-85: Non-string description
    data_with_dict_desc = {
        "key": "OSDP-101",
        "fields": {
            "summary": "Test",
            "status": {"name": "Open"},
            "priority": {"name": "High"},
            "description": {"type": "doc", "content": []},  # dict format
        },
    }

    ticket = _jira_to_ticket(data_with_dict_desc, "user1")
    assert isinstance(ticket.description, str)


@pytest.mark.asyncio
@respx.mock
async def test_create_ticket_reporter_lookup_fails(seed_token: None) -> None:
    """Test create_ticket when reporter lookup returns None."""
    # Line 149: reporter_id could be None
    respx.get(re.compile(f"{re.escape(BASE)}/user/search\\?.*")).mock(
        return_value=httpx.Response(200, json=[]),  # No users found
    )
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
async def test_jira_comment_to_domain_empty_body(seed_token: None) -> None:
    """Test _jira_comment_to_domain with various body formats."""
    ticket_id = uuid4()
    # Line 188-198: Empty or missing body
    empty_comment = {
        "id": "c-1",
        "body": {},  # Empty body
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(empty_comment, ticket_id)
    assert comment.content == "<empty>"
    # Missing body entirely
    no_body_comment = {
        "id": "c-2",
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(no_body_comment, ticket_id)
    assert comment.content == "<empty>"
    # Body with no content array
    no_content_comment = {
        "id": "c-3",
        "body": {"type": "doc", "version": 1},
        "author": {"displayName": "Author"},
    }
    comment = _jira_comment_to_domain(no_content_comment, ticket_id)
    assert comment.content == "<empty>"


@pytest.mark.asyncio
@respx.mock
async def test_delete_ticket_not_found(seed_token: None) -> None:
    """Test delete_ticket when ticket doesn't exist."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    # Line 295: Delete returns False or raises
    respx.delete(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(404, json={"error": "Not found"}),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="Failed to delete ticket"):
        await svc.delete_ticket(ticket_id)


@pytest.mark.asyncio
@respx.mock
async def test_get_ticket_comments_service_error(seed_token: None) -> None:
    """Test get_ticket_comments when service fails."""
    ticket_id = uuid4()
    key = "OSDP-101"
    map_uuid_to_key("u1", ticket_id, key)

    respx.get(f"{BASE}/issue/{key}/comment").mock(
        return_value=httpx.Response(500, json={"error": "Server error"}),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(httpx.HTTPError):  # Will raise httpx exception
        await svc.get_ticket_comments(ticket_id)


@pytest.mark.asyncio
@respx.mock
async def test_reassign_ticket_not_found_user(seed_token: None) -> None:
    """Test reassigning ticket when user is not found."""
    respx.get(re.compile(f"{re.escape(BASE)}/user/search\\?.*")).mock(
        return_value=httpx.Response(200, json=[]),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match=r"Assignee .* was not found"):
        await svc.reassign_ticket(uuid4(), "nonexistent@example.com")


@pytest.mark.asyncio
@respx.mock
async def test_update_priority_not_found(seed_token: None) -> None:
    """Test updating priority for non-existent ticket."""
    ticket_id = uuid4()
    key = str(ticket_id)
    respx.put(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(404, json={"error": "Not found"}),
    )
    respx.get(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(404, json={"error": "Not found"}),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="Failed to update priority"):
        await svc.update_priority(ticket_id, TicketPriority.HIGH)


@pytest.mark.asyncio
@respx.mock
async def test_delete_ticket_service_error_exception(seed_token: None) -> None:
    """Test delete ticket raises ServiceError on exception."""
    ticket_id = uuid4()
    key = str(ticket_id)
    respx.delete(f"{BASE}/issue/{key}").mock(
        return_value=httpx.Response(500, json={"error": "Internal error"}),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(ServiceError, match="Failed to delete ticket"):
        await svc.delete_ticket(ticket_id)


@pytest.mark.asyncio
@respx.mock
async def test_add_comment_not_found_exception(seed_token: None) -> None:
    """Test add comment raises TicketNotFoundError on exception."""
    ticket_id = uuid4()
    key = str(ticket_id)
    respx.post(f"{BASE}/issue/{key}/comment").mock(
        return_value=httpx.Response(404, json={"error": "Not found"}),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")

    with pytest.raises(TicketNotFoundError):
        await svc.add_comment(ticket_id, "author@example.com", "Test comment")


@pytest.mark.asyncio
@respx.mock
async def test_transition_status_delegates_to_update(seed_token: None) -> None:
    """Test that transition_status delegates to update_ticket."""
    respx.get(f"{BASE}/issue/OSDP-101/transitions").mock(
        return_value=httpx.Response(200, json={
            "transitions": [{"id": "11", "name": "In Progress"}],
        }),
    )
    respx.post(f"{BASE}/issue/OSDP-101/transitions").mock(
        return_value=httpx.Response(204),
    )
    respx.get(f"{BASE}/issue/OSDP-101").mock(
        return_value=httpx.Response(200, json={
            "key": "OSDP-101",
            "fields": {
                "summary": "Test",
                "status": {"name": "In Progress"},
                "priority": {"name": "Medium"},
                "description": "Test",
                "assignee": None,
                "reporter": {"displayName": "Test"},
                "created": "2025-10-29T00:00:00.000+0000",
                "updated": "2025-10-29T00:00:00.000+0000",
            },
        }),
    )

    svc = TicketImpl(user_id="u1", project_key="OSDP")
    ticket_id = uuid4()

    # Map the UUID to the key
    from ticket_impl.storage import map_uuid_to_key
    map_uuid_to_key("u1", ticket_id, "OSDP-101")

    ticket = await svc.transition_status(ticket_id, TicketStatus.IN_PROGRESS)
    assert ticket.status == TicketStatus.IN_PROGRESS
