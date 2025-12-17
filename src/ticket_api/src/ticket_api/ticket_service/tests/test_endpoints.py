"""Unit tests for Ticket Service API endpoints."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from ticket_api import TicketStatus
from ticket_api.ticket_impl.models import Comment, Ticket, TicketPriority

# Test constants
EXPECTED_TICKETS_COUNT = 2
DEFAULT_LIMIT = 100
DEFAULT_OFFSET = 0
CUSTOM_LIMIT = 10
CUSTOM_OFFSET = 5

# Mock environment variables BEFORE importing the app
with patch.dict(
    "os.environ",
    {
        "JIRA_CLOUD_ID": "test-cloud-id",
        "JIRA_CLIENT_ID": "test-client-id",
        "JIRA_CLIENT_SECRET": "test-client-secret",
        "JIRA_REDIRECT_URI": "http://localhost:8000/callback",
        "OAUTH_CLIENT_ID": "test-oauth-client-id",
        "OAUTH_CLIENT_SECRET": "test-oauth-client-secret",
        "OAUTH_REDIRECT_URI": "http://localhost:8000/callback",
    },
):
    from ticket_service.main import app


@pytest.fixture
def sample_ticket() -> Ticket:
    """Fixture providing a sample ticket."""
    return Ticket(
        id=uuid4(),
        title="Sample Ticket",
        description="This is a sample ticket",
        status=TicketStatus.OPEN,
        priority=TicketPriority.MEDIUM,
        reporter="reporter@example.com",
        assignee="assignee@example.com",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        comments=[],
    )


@pytest.fixture
def sample_tickets() -> list[Ticket]:
    """Fixture providing multiple sample tickets."""
    return [
        Ticket(
            id=uuid4(),
            title="Ticket 1",
            description="First ticket",
            status=TicketStatus.OPEN,
            priority=TicketPriority.HIGH,
            reporter="reporter@example.com",
            assignee="assignee@example.com",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            comments=[],
        ),
        Ticket(
            id=uuid4(),
            title="Ticket 2",
            description="Second ticket",
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.MEDIUM,
            reporter="reporter@example.com",
            assignee=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            comments=[],
        ),
    ]


@pytest.fixture
def sample_comment(sample_ticket: Ticket) -> Comment:
    """Fixture providing a sample comment."""
    return Comment(
        id=uuid4(),
        ticket_id=sample_ticket.id,
        author="commenter@example.com",
        content="This is a test comment",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Fixture providing an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, async_client: AsyncClient) -> None:
        """Test health check returns 200 with correct response."""
        response = await async_client.get("/health")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ticket_service"
        assert data["version"] == "0.1.0"


class TestCreateTicket:
    """Tests for POST /api/v1/tickets endpoint."""

    @pytest.mark.asyncio
    async def test_create_ticket_success(
        self,
        async_client: AsyncClient,
        sample_ticket: Ticket,
    ) -> None:
        """Test successfully creating a ticket."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.create_ticket.return_value = sample_ticket
            mock_impl.return_value = mock_service

            response = await async_client.post(
                "/api/v1/tickets",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
                json={
                    "title": "Sample Ticket",
                    "description": "This is a sample ticket",
                    "reporter": "reporter@example.com",
                    "priority": "medium",
                    "assignee": "assignee@example.com",
                },
            )

            assert response.status_code == HTTPStatus.CREATED
            data = response.json()
            assert data["title"] == "Sample Ticket"
            assert data["status"] == "open"

    @pytest.mark.asyncio
    async def test_create_ticket_invalid_data(self, async_client: AsyncClient) -> None:
        """Test creating a ticket with invalid data returns 422."""
        response = await async_client.post(
            "/api/v1/tickets",
            headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            json={
                "title": "",  # Empty title
                "description": "Test",
                "reporter": "reporter@example.com",
                "priority": "medium",
            },
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_ticket_missing_auth(self, async_client: AsyncClient) -> None:
        """Test creating a ticket without authentication returns 401."""
        response = await async_client.post(
            "/api/v1/tickets",
            json={
                "title": "Test Ticket",
                "description": "Test",
                "reporter": "reporter@example.com",
                "priority": "medium",
            },
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_create_ticket_service_error(self, async_client: AsyncClient) -> None:
        """Test creating a ticket when service fails returns 500."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.create_ticket.side_effect = Exception("Database error")
            mock_impl.return_value = mock_service

            response = await async_client.post(
                "/api/v1/tickets",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
                json={
                    "title": "Test Ticket",
                    "description": "Test",
                    "reporter": "reporter@example.com",
                    "priority": "medium",
                },
            )

            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            assert "Failed to create ticket" in response.json()["detail"]


class TestGetTicket:
    """Tests for GET /api/v1/tickets/{ticket_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_ticket_success(
        self,
        async_client: AsyncClient,
        sample_ticket: Ticket,
    ) -> None:
        """Test successfully retrieving a ticket."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.get_ticket.return_value = sample_ticket
            mock_impl.return_value = mock_service

            response = await async_client.get(
                f"/api/v1/tickets/{sample_ticket.id}",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert data["title"] == sample_ticket.title
            assert str(data["id"]) == str(sample_ticket.id)

    @pytest.mark.asyncio
    async def test_get_ticket_not_found(self, async_client: AsyncClient) -> None:
        """Test retrieving a non-existent ticket returns 404."""
        ticket_id = uuid4()
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.get_ticket.return_value = None
            mock_impl.return_value = mock_service

            response = await async_client.get(
                f"/api/v1/tickets/{ticket_id}",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_ticket_missing_auth(self, async_client: AsyncClient) -> None:
        """Test retrieving a ticket without authentication returns 401."""
        ticket_id = uuid4()
        response = await async_client.get(f"/api/v1/tickets/{ticket_id}")

        assert response.status_code == HTTPStatus.UNAUTHORIZED


class TestListTickets:
    """Tests for GET /api/v1/tickets endpoint."""

    @pytest.mark.asyncio
    async def test_list_tickets_success(
        self,
        async_client: AsyncClient,
        sample_tickets: list[Ticket],
    ) -> None:
        """Test successfully listing tickets."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.list_tickets.return_value = sample_tickets
            mock_impl.return_value = mock_service

            response = await async_client.get(
                "/api/v1/tickets",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert len(data["tickets"]) == EXPECTED_TICKETS_COUNT
            assert data["total"] == EXPECTED_TICKETS_COUNT
            assert data["limit"] == DEFAULT_LIMIT
            assert data["offset"] == DEFAULT_OFFSET

    @pytest.mark.asyncio
    async def test_list_tickets_empty(self, async_client: AsyncClient) -> None:
        """Test listing tickets when none exist returns empty list."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.list_tickets.return_value = []
            mock_impl.return_value = mock_service

            response = await async_client.get(
                "/api/v1/tickets",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert len(data["tickets"]) == 0
            assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_tickets_with_filters(
        self,
        async_client: AsyncClient,
        sample_tickets: list[Ticket],
    ) -> None:
        """Test listing tickets with status filter."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.list_tickets.return_value = [sample_tickets[0]]
            mock_impl.return_value = mock_service

            response = await async_client.get(
                "/api/v1/tickets",
                params={"status": "open", "assignee": "assignee@example.com"},
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert len(data["tickets"]) == 1

    @pytest.mark.asyncio
    async def test_list_tickets_with_pagination(
        self,
        async_client: AsyncClient,
        sample_tickets: list[Ticket],
    ) -> None:
        """Test listing tickets with pagination."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.list_tickets.return_value = [sample_tickets[0]]
            mock_impl.return_value = mock_service

            response = await async_client.get(
                "/api/v1/tickets",
                params={"limit": CUSTOM_LIMIT, "offset": CUSTOM_OFFSET},
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert data["limit"] == CUSTOM_LIMIT
            assert data["offset"] == CUSTOM_OFFSET

    @pytest.mark.asyncio
    async def test_list_tickets_missing_auth(self, async_client: AsyncClient) -> None:
        """Test listing tickets without authentication returns 401."""
        response = await async_client.get("/api/v1/tickets")

        assert response.status_code == HTTPStatus.UNAUTHORIZED


class TestUpdateTicket:
    """Tests for PATCH /api/v1/tickets/{ticket_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_ticket_success(
        self,
        async_client: AsyncClient,
        sample_ticket: Ticket,
    ) -> None:
        """Test successfully updating a ticket."""
        updated_ticket = Ticket(
            id=sample_ticket.id,
            title="Updated Title",
            description=sample_ticket.description,
            status=TicketStatus.IN_PROGRESS,
            priority=TicketPriority.HIGH,
            reporter=sample_ticket.reporter,
            assignee=sample_ticket.assignee,
            created_at=sample_ticket.created_at,
            updated_at=datetime.now(UTC),
            comments=[],
        )

        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.update_ticket.return_value = updated_ticket
            mock_impl.return_value = mock_service

            response = await async_client.patch(
                f"/api/v1/tickets/{sample_ticket.id}",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
                json={
                    "title": "Updated Title",
                    "status": "in_progress",
                    "priority": "high",
                },
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert data["title"] == "Updated Title"
            assert data["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_update_ticket_not_found(self, async_client: AsyncClient) -> None:
        """Test updating a non-existent ticket returns 404."""
        ticket_id = uuid4()
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.update_ticket.return_value = None
            mock_impl.return_value = mock_service

            response = await async_client.patch(
                f"/api/v1/tickets/{ticket_id}",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
                json={"title": "New Title"},
            )

            assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_ticket_missing_auth(self, async_client: AsyncClient) -> None:
        """Test updating a ticket without authentication returns 401."""
        ticket_id = uuid4()
        response = await async_client.patch(
            f"/api/v1/tickets/{ticket_id}",
            json={"title": "New Title"},
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED


class TestDeleteTicket:
    """Tests for DELETE /api/v1/tickets/{ticket_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_ticket_success(
        self,
        async_client: AsyncClient,
        sample_ticket: Ticket,
    ) -> None:
        """Test successfully deleting a ticket."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.delete_ticket.return_value = True
            mock_impl.return_value = mock_service

            response = await async_client.delete(
                f"/api/v1/tickets/{sample_ticket.id}",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.NO_CONTENT

    @pytest.mark.asyncio
    async def test_delete_ticket_not_found(self, async_client: AsyncClient) -> None:
        """Test deleting a non-existent ticket returns 404."""
        ticket_id = uuid4()
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.delete_ticket.return_value = False
            mock_impl.return_value = mock_service

            response = await async_client.delete(
                f"/api/v1/tickets/{ticket_id}",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_ticket_missing_auth(self, async_client: AsyncClient) -> None:
        """Test deleting a ticket without authentication returns 401."""
        ticket_id = uuid4()
        response = await async_client.delete(f"/api/v1/tickets/{ticket_id}")

        assert response.status_code == HTTPStatus.UNAUTHORIZED


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_oauth_login(self, async_client: AsyncClient) -> None:
        """Test OAuth login endpoint returns auth URL in JSON."""
        response = await async_client.get("/api/v1/auth/login", follow_redirects=False)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "auth_url" in data
        assert "auth.atlassian.com" in data["auth_url"]
        assert "authorize" in data["auth_url"]
        assert "state" in data
        assert "user_id" in data
        assert "status_code" in data
        assert data["status_code"] == HTTPStatus.FOUND.value
        assert "message" in data

    @pytest.mark.asyncio
    async def test_oauth_callback_invalid_state(self, async_client: AsyncClient) -> None:
        """Test OAuth callback with invalid state returns 400."""
        response = await async_client.get(
            "/api/v1/auth/callback?code=test-code&state=invalid-state",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "Invalid or expired state" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_oauth_callback_exchange_error(self, async_client: AsyncClient) -> None:
        """Test OAuth callback when token exchange fails."""
        with patch("ticket_service.main.exchange_code_for_tokens") as mock_exchange:
            mock_exchange.side_effect = Exception("Token exchange failed")
            # Store a valid state
            from ticket_service.main import _oauth_state_store

            state = "valid-test-state"
            _oauth_state_store[state] = "test-user-id"

            response = await async_client.get(f"/api/v1/auth/callback?code=test-code&state={state}")

            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            assert "OAuth callback failed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_auth_status_not_authenticated(self, async_client: AsyncClient) -> None:
        """Test checking auth status when not authenticated."""
        response = await async_client.get("/api/v1/auth/status")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["authenticated"] is False

    @pytest.mark.asyncio
    async def test_logout_not_authenticated(self, async_client: AsyncClient) -> None:
        """Test logout when not authenticated returns 401."""
        response = await async_client.post("/api/v1/auth/logout")

        assert response.status_code == HTTPStatus.UNAUTHORIZED


class TestCommentEndpoints:
    """Tests for comment-related endpoints."""

    @pytest.mark.asyncio
    async def test_add_comment_success(
        self,
        async_client: AsyncClient,
        sample_ticket: Ticket,
        sample_comment: Comment,
    ) -> None:
        """Test successfully adding a comment."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.add_comment.return_value = sample_comment
            mock_impl.return_value = mock_service

            response = await async_client.post(
                f"/api/v1/tickets/{sample_ticket.id}/comments",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
                json={
                    "author": "commenter@example.com",
                    "content": "This is a test comment",
                },
            )

            assert response.status_code == HTTPStatus.CREATED
            data = response.json()
            assert data["content"] == "This is a test comment"
            assert data["author"] == "commenter@example.com"

    @pytest.mark.asyncio
    async def test_add_comment_ticket_not_found(self, async_client: AsyncClient) -> None:
        """Test adding a comment to non-existent ticket returns 404."""
        ticket_id = uuid4()
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.add_comment.return_value = None
            mock_impl.return_value = mock_service

            response = await async_client.post(
                f"/api/v1/tickets/{ticket_id}/comments",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
                json={
                    "author": "commenter@example.com",
                    "content": "Test comment",
                },
            )

            assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_add_comment_missing_auth(self, async_client: AsyncClient) -> None:
        """Test adding a comment without authentication returns 401."""
        ticket_id = uuid4()
        response = await async_client.post(
            f"/api/v1/tickets/{ticket_id}/comments",
            json={
                "author": "commenter@example.com",
                "content": "Test comment",
            },
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_comments_success(
        self,
        async_client: AsyncClient,
        sample_ticket: Ticket,
        sample_comment: Comment,
    ) -> None:
        """Test successfully retrieving comments."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.get_ticket_comments.return_value = [sample_comment]
            mock_impl.return_value = mock_service

            response = await async_client.get(
                f"/api/v1/tickets/{sample_ticket.id}/comments",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["content"] == "This is a test comment"

    @pytest.mark.asyncio
    async def test_get_comments_empty(
        self,
        async_client: AsyncClient,
        sample_ticket: Ticket,
    ) -> None:
        """Test retrieving comments when none exist returns empty list."""
        with patch("ticket_service.main.TicketImpl") as mock_impl:
            mock_service = AsyncMock()
            mock_service.get_ticket_comments.return_value = []
            mock_impl.return_value = mock_service

            response = await async_client.get(
                f"/api/v1/tickets/{sample_ticket.id}/comments",
                headers={"X-User-ID": "test-user", "X-Project-Key": "TEST"},
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert len(data) == 0

    @pytest.mark.asyncio
    async def test_get_comments_missing_auth(self, async_client: AsyncClient) -> None:
        """Test retrieving comments without authentication returns 401."""
        ticket_id = uuid4()
        response = await async_client.get(f"/api/v1/tickets/{ticket_id}/comments")

        assert response.status_code == HTTPStatus.UNAUTHORIZED
