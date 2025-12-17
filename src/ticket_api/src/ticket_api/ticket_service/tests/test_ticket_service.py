"""Unit tests for Comment endpoints in the Ticket Service API."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from ticket_api.ticket_impl.models import Comment

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
def mock_user_id() -> str:
    """Fixture providing a mock user ID."""
    return str(uuid4())


@pytest.fixture
def mock_project_key() -> str:
    """Fixture providing a mock Jira project key."""
    return "TEST"


@pytest.fixture
def mock_ticket_id() -> UUID:
    """Fixture providing a mock ticket ID."""
    return uuid4()


@pytest.fixture
def mock_comment() -> Comment:
    """Fixture providing a mock Comment object."""
    return Comment(
        id=uuid4(),
        ticket_id=uuid4(),
        author="developer@example.com",
        content="This is a test comment",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_comments() -> list[Comment]:
    """Fixture providing a list of mock Comments."""
    ticket_id = uuid4()
    return [
        Comment(
            id=uuid4(),
            ticket_id=ticket_id,
            author="user1@example.com",
            content="First comment",
            created_at=datetime.now(UTC),
        ),
        Comment(
            id=uuid4(),
            ticket_id=ticket_id,
            author="user2@example.com",
            content="Second comment",
            created_at=datetime.now(UTC),
        ),
    ]


@pytest.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Fixture providing an async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestAddComment:
    """Tests for POST /api/v1/tickets/{ticket_id}/comments endpoint."""

    @pytest.mark.asyncio
    async def test_add_comment_success(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
        mock_ticket_id: UUID,
        mock_comment: Comment,
    ) -> None:
        """Test successfully adding a comment to a ticket."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            # Setup mock service
            mock_service = AsyncMock()
            mock_service.add_comment.return_value = mock_comment
            mock_impl.return_value = mock_service

            response = await async_client.post(
                f"/api/v1/tickets/{mock_ticket_id}/comments",
                headers={
                    "X-User-ID": mock_user_id,
                    "X-Project-Key": mock_project_key,
                },
                json={
                    "author": "developer@example.com",
                    "content": "This is a test comment",
                },
            )

            assert response.status_code == HTTPStatus.CREATED
            data = response.json()
            assert data["author"] == mock_comment.author
            assert data["content"] == mock_comment.content
            assert "id" in data
            assert "created_at" in data

            # Verify service was called correctly
            mock_service.add_comment.assert_called_once_with(
                ticket_id=mock_ticket_id,
                author="developer@example.com",
                content="This is a test comment",
            )

    @pytest.mark.asyncio
    async def test_add_comment_ticket_not_found(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
        mock_ticket_id: UUID,
    ) -> None:
        """Test adding a comment to a non-existent ticket returns 404."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.add_comment.return_value = None  # Ticket not found
            mock_impl.return_value = mock_service

            response = await async_client.post(
                f"/api/v1/tickets/{mock_ticket_id}/comments",
                headers={
                    "X-User-ID": mock_user_id,
                    "X-Project-Key": mock_project_key,
                },
                json={
                    "author": "developer@example.com",
                    "content": "This is a test comment",
                },
            )

            assert response.status_code == HTTPStatus.NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_add_comment_invalid_data(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
        mock_ticket_id: UUID,
    ) -> None:
        """Test adding a comment with invalid data returns 422."""
        with patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}):
            response = await async_client.post(
                f"/api/v1/tickets/{mock_ticket_id}/comments",
                headers={
                    "X-User-ID": mock_user_id,
                    "X-Project-Key": mock_project_key,
                },
                json={
                    "author": "",  # Empty author - should fail validation
                    "content": "This is a test comment",
                },
            )

            assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_add_comment_missing_auth(
        self,
        async_client: AsyncClient,
        mock_ticket_id: UUID,
    ) -> None:
        """Test adding a comment without authentication returns 401."""
        response = await async_client.post(
            f"/api/v1/tickets/{mock_ticket_id}/comments",
            json={
                "author": "developer@example.com",
                "content": "This is a test comment",
            },
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED  # Missing required headers

    @pytest.mark.asyncio
    async def test_add_comment_service_error(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
        mock_ticket_id: UUID,
    ) -> None:
        """Test adding a comment with service error returns 500."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.add_comment.side_effect = Exception("Database error")
            mock_impl.return_value = mock_service

            response = await async_client.post(
                f"/api/v1/tickets/{mock_ticket_id}/comments",
                headers={
                    "X-User-ID": mock_user_id,
                    "X-Project-Key": mock_project_key,
                },
                json={
                    "author": "developer@example.com",
                    "content": "This is a test comment",
                },
            )

            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            assert "Failed to add comment" in response.json()["detail"]


class TestGetTicketComments:
    """Tests for GET /api/v1/tickets/{ticket_id}/comments endpoint."""

    @pytest.mark.asyncio
    async def test_get_comments_success(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
        mock_ticket_id: UUID,
        mock_comments: list[Comment],
    ) -> None:
        """Test successfully retrieving all comments for a ticket."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.get_ticket_comments.return_value = mock_comments
            mock_impl.return_value = mock_service

            response = await async_client.get(
                f"/api/v1/tickets/{mock_ticket_id}/comments",
                headers={
                    "X-User-ID": mock_user_id,
                    "X-Project-Key": mock_project_key,
                },
            )

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert len(data) == len(mock_comments)
            assert data[0]["author"] == mock_comments[0].author
            assert data[1]["author"] == mock_comments[1].author

            mock_service.get_ticket_comments.assert_called_once_with(mock_ticket_id)

    @pytest.mark.asyncio
    async def test_get_comments_empty_list(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
        mock_ticket_id: UUID,
    ) -> None:
        """Test retrieving comments for a ticket with no comments returns empty list."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.get_ticket_comments.return_value = []
            mock_impl.return_value = mock_service

            response = await async_client.get(
                f"/api/v1/tickets/{mock_ticket_id}/comments",
                headers={
                    "X-User-ID": mock_user_id,
                    "X-Project-Key": mock_project_key,
                },
            )

            assert response.status_code == HTTPStatus.OK
            assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_comments_missing_auth(
        self,
        async_client: AsyncClient,
        mock_ticket_id: UUID,
    ) -> None:
        """Test retrieving comments without authentication returns 401."""
        response = await async_client.get(
            f"/api/v1/tickets/{mock_ticket_id}/comments",
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED  # Missing required headers

    @pytest.mark.asyncio
    async def test_get_comments_invalid_user(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
        mock_ticket_id: UUID,
    ) -> None:
        """Test retrieving comments with invalid user returns 401."""
        with patch("ticket_service.main.get_user_tokens", return_value=None):
            response = await async_client.get(
                f"/api/v1/tickets/{mock_ticket_id}/comments",
                headers={
                    "X-User-ID": mock_user_id,
                    "X-Project-Key": mock_project_key,
                },
            )

            assert response.status_code == HTTPStatus.UNAUTHORIZED
            assert "session expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_ticket_value_error(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
    ) -> None:
        """Test create ticket with invalid input."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.create_ticket.side_effect = ValueError("bad input")
            mock_impl.return_value = mock_service
            resp = await async_client.post(
                "/api/v1/tickets",
                headers={"X-User-ID": mock_user_id, "X-Project-Key": mock_project_key},
                json={"title": "t", "description": "d", "reporter": "r"},
            )
            assert resp.status_code == HTTPStatus.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_ticket_not_found(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
    ) -> None:
        """Test get ticket when ticket is not found."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.get_ticket.return_value = None
            mock_impl.return_value = mock_service
            ticket_id = str(uuid4())
            resp = await async_client.get(
                f"/api/v1/tickets/{ticket_id}",
                headers={"X-User-ID": mock_user_id, "X-Project-Key": mock_project_key},
            )
            assert resp.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_ticket_comments_exception(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
    ) -> None:
        """Test get ticket comments when an exception occurs."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.get_ticket.return_value = AsyncMock()
            mock_service.get_ticket_comments.side_effect = Exception("fail")
            mock_impl.return_value = mock_service
            ticket_id = str(uuid4())
            resp = await async_client.get(
                f"/api/v1/tickets/{ticket_id}",
                headers={"X-User-ID": mock_user_id, "X-Project-Key": mock_project_key},
            )
            assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_list_tickets_value_error(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
    ) -> None:
        """Test list tickets with invalid input."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.list_tickets.side_effect = ValueError("bad params")
            mock_impl.return_value = mock_service
            resp = await async_client.get(
                "/api/v1/tickets",
                headers={"X-User-ID": mock_user_id, "X-Project-Key": mock_project_key},
            )
            assert resp.status_code == HTTPStatus.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_list_tickets_exception(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
    ) -> None:
        """Test list tickets when an exception occurs."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.list_tickets.side_effect = Exception("fail")
            mock_impl.return_value = mock_service
            resp = await async_client.get(
                "/api/v1/tickets",
                headers={"X-User-ID": mock_user_id, "X-Project-Key": mock_project_key},
            )
            assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_update_ticket_exception(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
    ) -> None:
        """Test update ticket when an exception occurs."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.update_ticket.side_effect = Exception("fail")
            mock_impl.return_value = mock_service
            ticket_id = str(uuid4())
            resp = await async_client.patch(
                f"/api/v1/tickets/{ticket_id}",
                headers={"X-User-ID": mock_user_id, "X-Project-Key": mock_project_key},
                json={},
            )
            assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_update_ticket_not_found(
        self,
        async_client: AsyncClient,
        mock_user_id: str,
        mock_project_key: str,
    ) -> None:
        """Test update ticket when ticket is not found."""
        with (
            patch("ticket_service.main.get_user_tokens", return_value={"access_token": "fake"}),
            patch("ticket_service.main.TicketImpl") as mock_impl,
        ):
            mock_service = AsyncMock()
            mock_service.update_ticket.return_value = None
            mock_impl.return_value = mock_service
            ticket_id = str(uuid4())
            resp = await async_client.patch(
                f"/api/v1/tickets/{ticket_id}",
                headers={"X-User-ID": mock_user_id, "X-Project-Key": mock_project_key},
                json={},
            )
            assert resp.status_code == HTTPStatus.NOT_FOUND
