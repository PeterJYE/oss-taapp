"""Main FastAPI application for the Ticket Service.

This service exposes the TicketImpl (from ticket_impl) over HTTP endpoints,
providing a REST API for ticket management operations.
"""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated, NamedTuple
from uuid import UUID, uuid4

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from ticket_api.ticket_impl.interface import TicketServiceAPI
from ticket_api.ticket_impl.exceptions import ServiceError
from ticket_api.ticket_impl.models import TicketStatus
from ticket_api.ticket_impl.src.ticket_impl import TicketImpl
from ticket_api.ticket_impl.src.ticket_impl.oauth import build_authorize_url, exchange_code_for_tokens
from ticket_api.ticket_impl.src.ticket_impl.storage import clear_user_tokens, get_user_tokens

from ticket_service.models import (
    CommentCreateRequest,
    CommentResponse,
    HealthResponse,
    TicketCreateRequest,
    TicketListResponse,
    TicketResponse,
    TicketUpdateRequest,
)

logger = logging.getLogger("ticket_service")

# ============================================================================
# APPLICATION SETUP
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan events."""
    logger.info("Starting %s v%s", app.title, app.version)
    yield
    logger.info("Shutting down %s", app.title)


app = FastAPI(
    title="Ticket Service",
    description="REST API for ticket management backed by Jira",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS - allow credentials for cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,  # Important for cookies!
    allow_methods=["*"],
    allow_headers=["*"],
)

_oauth_state_store: dict[str, str] = {}

# ============================================================================
# DEPENDENCIES - Cookie-based authentication (hidden from Swagger)
# ============================================================================


async def get_session_user_id(
    session_user_id: Annotated[str | None, Cookie(alias="user_id", include_in_schema=False)] = None,
) -> str | None:
    """Extract user_id from cookie without showing in API docs."""
    return session_user_id


async def get_user_id(
    session_user_id: Annotated[str | None, Depends(get_session_user_id)] = None,
    x_user_id: Annotated[
        str | None,
        Header(
            description="User ID for authentication (fallback)",
            include_in_schema=False,
        ),
    ] = None,
) -> str:
    """Extract user ID from cookie (preferred) or X-User-ID header (fallback).

    Priority:
    1. Cookie (automatic from browser/Swagger)
    2. X-User-ID header (for programmatic access)
    3. test- prefix users (for testing)
    """
    # Try cookie first (automatic session)
    user_id = session_user_id or x_user_id

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please login at /api/v1/auth/login",
        )

    # Allow test users to bypass OAuth for testing/development
    if user_id.startswith("test-"):
        return user_id

    # Verify user has valid OAuth tokens
    tokens = get_user_tokens(user_id)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please login again at /api/v1/auth/login",
        )

    return user_id


async def get_project_key(
    x_project_key: Annotated[str, Header(..., description="Jira project key")],
) -> str:
    """Extract Jira project key from X-Project-Key header."""
    if not x_project_key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Missing X-Project-Key header",
        )
    return x_project_key


async def get_ticket_service(
    user_id: Annotated[str, Depends(get_user_id)],
    project_key: Annotated[str, Depends(get_project_key)],
) -> TicketServiceAPI:
    """Provide the concrete TicketImpl instance."""
    return TicketImpl(user_id=user_id, project_key=project_key)


# ============================================================================
# OAUTH ENDPOINTS - Cookie-based session management
# ============================================================================


@app.get(
    "/api/v1/auth/login",
    tags=["authentication"],
    summary="Initiate OAuth 2.0 flow",
    status_code=HTTPStatus.OK,
    description="Get the OAuth 2.0 authorization URL for Jira.",
)
async def oauth_login(
    session_user_id: Annotated[str | None, Depends(get_session_user_id)] = None,
) -> dict[str, str | int | bool]:
    """Get the OAuth 2.0 authorization URL for Jira."""
    # Check if user already has an active session
    if session_user_id:
        if session_user_id.startswith("test-"):
            return {
                "already_authenticated": True,
                "user_id": session_user_id,
                "message": "You already have an active test user session",
            }
        tokens = get_user_tokens(session_user_id)
        if tokens:
            return {
                "already_authenticated": True,
                "user_id": session_user_id,
                "message": "You already have an active session with valid OAuth tokens",
            }

    # Generate new OAuth flow
    try:
        user_id = str(uuid4())
        state = secrets.token_urlsafe(32)
        _oauth_state_store[state] = user_id
        auth_url = build_authorize_url(state=state)
    except Exception as e:
        logger.exception("Failed to build OAuth authorization URL")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OAuth flow: {e!s}",
        ) from e
    else:
        return {
            "already_authenticated": False,
            "auth_url": auth_url,
            "message": "Open the auth_url in your browser to complete authentication",
            "state": state,
            "user_id": user_id,
            "status_code": 302,
            "redirect_to": auth_url,
        }


@app.get(
    "/api/v1/auth/callback",
    tags=["authentication"],
    summary="OAuth 2.0 callback endpoint",
)
async def oauth_callback(
    response: Response,
    code: Annotated[str, Query(..., description="Authorization code from Jira")],
    state: Annotated[str, Query(..., description="State for CSRF protection")],
) -> dict[str, str]:
    """Handle OAuth callback and set session cookie."""
    if state not in _oauth_state_store:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )

    user_id = _oauth_state_store.pop(state)

    try:
        await exchange_code_for_tokens(user_id=user_id, code=code)
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {e!s}",
        ) from e

    # Set HTTP-only cookie with user_id
    response.set_cookie(
        key="user_id",
        value=user_id,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=86400 * 30,  # 30 days
    )

    return {
        "message": "Authentication successful",
        "user_id": user_id,
        "instructions": "Session cookie set. You can now make API requests without User-ID header.",
    }


@app.get(
    "/api/v1/auth/status",
    tags=["authentication"],
    summary="Check authentication status",
)
async def auth_status(
    session_user_id: Annotated[str | None, Depends(get_session_user_id)] = None,
) -> dict[str, bool | str]:
    """Check if the current session is authenticated.

    No parameters needed - automatically checks session cookie.
    """
    if not session_user_id:
        return {
            "authenticated": False,
            "message": "Not authenticated. Please login at /api/v1/auth/login",
        }

    # Check if session has valid tokens
    if session_user_id.startswith("test-"):
        return {
            "authenticated": True,
            "user_id": session_user_id,
            "message": "Test user session active",
        }

    tokens = get_user_tokens(session_user_id)
    if not tokens:
        return {
            "authenticated": False,
            "message": "Session expired. Please login again at /api/v1/auth/login",
        }

    return {
        "authenticated": True,
        "user_id": session_user_id,
        "message": "Session is valid",
    }


@app.post(
    "/api/v1/auth/logout",
    tags=["authentication"],
    summary="Logout and revoke tokens",
    status_code=HTTPStatus.OK,
)
async def logout(
    response: Response,
    session_user_id: Annotated[str | None, Depends(get_session_user_id)] = None,
) -> dict[str, str]:
    """Logout by clearing session cookie and stored tokens.

    No parameters needed - automatically uses session cookie.
    """
    if not session_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Nothing to logout.",
        )

    # Clear tokens from database
    clear_user_tokens(session_user_id)
    response.delete_cookie(key="user_id")

    return {
        "message": "Successfully logged out",
        "user_id": session_user_id,
    }


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> HealthResponse:
    """Verify that the service is running and responsive."""
    return HealthResponse(status="healthy", service="ticket_service", version="0.1.0")


# ============================================================================
# TICKET ENDPOINTS - All use cookie-based authentication automatically
# ============================================================================


@app.post("/api/v1/tickets", status_code=status.HTTP_201_CREATED, tags=["tickets"])
async def create_ticket(
    request: TicketCreateRequest,
    service: Annotated[TicketServiceAPI, Depends(get_ticket_service)],
) -> TicketResponse:
    """Create a new ticket.

    Authentication is automatic via session cookie. Only X-Project-Key header is required.
    """
    try:
        ticket = await service.create_ticket(
            title=request.title,
            description=request.description,
            reporter=request.reporter,
            priority=request.priority,
            assignee=request.assignee,
        )
        return TicketResponse.model_validate(ticket)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ticket: {e!s}",
        ) from e


@app.get(
    "/api/v1/tickets/{ticket_id}",
    tags=["tickets"],
    summary="Get a ticket by ID",
)
async def get_ticket(
    ticket_id: UUID,
    service: Annotated[TicketServiceAPI, Depends(get_ticket_service)],
) -> TicketResponse:
    """Retrieve a specific ticket by its UUID.

    Returns 404 if the ticket is not found.
    """
    ticket = await service.get_ticket(ticket_id)
    if ticket is None:
        msg = f"Ticket {ticket_id} not found"
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=msg,
        )

    try:
        # Fetch comments for the ticket
        comments = await service.get_ticket_comments(ticket_id)

        # Create response with comments
        ticket_dict = ticket.model_dump() if hasattr(ticket, "model_dump") else ticket.__dict__
        ticket_dict["comments"] = [
            CommentResponse.model_validate(
                c.model_dump() if hasattr(c, "model_dump") else c.__dict__,
            )
            for c in comments
        ]

        return TicketResponse.model_validate(ticket_dict)
    except Exception as e:
        logger.exception("Failed to get ticket %s", ticket_id)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ticket: {e!s}",
        ) from e


class TicketFilters(NamedTuple):
    """Grouped ticket filtering parameters."""

    status: TicketStatus | None
    assignee: str | None
    reporter: str | None


async def get_ticket_filters(
    status_filter: Annotated[
        TicketStatus | None,
        Query(alias="status", description="Filter by ticket status"),
    ] = None,
    assignee: Annotated[
        str | None,
        Query(description="Filter by assignee username/email"),
    ] = None,
    reporter: Annotated[
        str | None,
        Query(description="Filter by reporter username/email"),
    ] = None,
) -> TicketFilters:
    """Dependency that groups ticket filtering parameters into a single object."""
    return TicketFilters(status=status_filter, assignee=assignee, reporter=reporter)


@app.get(
    "/api/v1/tickets",
    tags=["tickets"],
    summary="List tickets with filtering",
)
async def list_tickets(
    service: Annotated[TicketServiceAPI, Depends(get_ticket_service)],
    filters: Annotated[TicketFilters, Depends(get_ticket_filters)],
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Maximum number of tickets to return"),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of tickets to skip"),
    ] = 0,
) -> TicketListResponse:
    """List tickets with optional filtering and pagination.

    All filter parameters are optional. Results are paginated using limit/offset.
    """
    try:
        tickets = await service.list_tickets(
            status=filters.status,
            assignee=filters.assignee,
            reporter=filters.reporter,
            limit=limit,
            offset=offset,
        )

        ticket_responses = [TicketResponse.model_validate(t) for t in tickets]

        return TicketListResponse(
            tickets=ticket_responses,
            total=len(ticket_responses),
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tickets: {e!s}",
        ) from e


@app.patch(
    "/api/v1/tickets/{ticket_id}",
    tags=["tickets"],
    summary="Update a ticket",
)
async def update_ticket(
    ticket_id: UUID,
    request: TicketUpdateRequest,
    service: Annotated[TicketServiceAPI, Depends(get_ticket_service)],
) -> TicketResponse:
    """Update an existing ticket. All fields are optional - only provided fields will be updated.

    Returns 404 if the ticket is not found.
    """
    # Always call update_ticket to check if ticket exists and apply any status changes
    # (other fields like title, description, priority are not yet supported by TicketImpl)
    try:
        ticket = await service.update_ticket(
            ticket_id=ticket_id,
            status=request.status,
        )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to update ticket: {e!s}",
        ) from e

    # Verify ticket exists
    if ticket is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    # Handle assignee separately if provided (skip if user not found)
    if request.assignee:
        try:
            ticket = await service.reassign_ticket(ticket_id, request.assignee)
        except (ServiceError, ValueError):
            # If assignee reassignment fails (user not found), just log and continue
            logger.warning("Failed to reassign ticket to %s", request.assignee)
            # ticket already has the latest state from update_ticket

    # Note: title, description, and priority updates are not yet supported
    # by the TicketImpl backend and would require implementation
    try:
        return TicketResponse.model_validate(ticket)
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate ticket: {e!s}",
        ) from e


@app.delete(
    "/api/v1/tickets/{ticket_id}",
    status_code=HTTPStatus.NO_CONTENT,
    tags=["tickets"],
    summary="Delete a ticket",
)
async def delete_ticket(
    ticket_id: UUID,
    service: Annotated[TicketServiceAPI, Depends(get_ticket_service)],
) -> None:
    """Delete a ticket permanently.

    Returns 404 if the ticket is not found.
    """
    success = await service.delete_ticket(ticket_id)
    if not success:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )


# ============================================================================
# COMMENT ENDPOINTS
# ============================================================================


@app.post(
    "/api/v1/tickets/{ticket_id}/comments",
    status_code=status.HTTP_201_CREATED,
    tags=["comments"],
    summary="Add a comment to a ticket",
)
async def add_comment(
    ticket_id: UUID,
    request: CommentCreateRequest,
    service: Annotated[TicketServiceAPI, Depends(get_ticket_service)],
) -> CommentResponse:
    """Add a new comment to an existing ticket.

    Returns 404 if the ticket is not found.
    """
    try:
        comment = await service.add_comment(
            ticket_id=ticket_id,
            author=request.author,
            content=request.content,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to add comment: {e!s}",
        ) from e
    if comment is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )
    return CommentResponse.model_validate(comment)


@app.get(
    "/api/v1/tickets/{ticket_id}/comments",
    tags=["comments"],
    summary="Get all comments for a ticket",
)
async def get_ticket_comments(
    ticket_id: UUID,
    service: Annotated[TicketServiceAPI, Depends(get_ticket_service)],
) -> list[CommentResponse]:
    """Retrieve all comments for a specific ticket.

    Returns an empty list if the ticket has no comments or is not found.
    """
    comments = await service.get_ticket_comments(ticket_id)
    return [CommentResponse.model_validate(c) for c in comments]
