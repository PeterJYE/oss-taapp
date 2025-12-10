"""Pydantic schemas for API request/response models.

These models define the shape of data coming into and going out of the API endpoints.
They provide validation, serialization, and documentation for the OpenAPI spec.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from ticket_api import TicketStatus
from ticket_api.ticket_impl.models import TicketPriority

# ============================================================================
# REQUEST MODELS - Used for incoming data validation
# ============================================================================


class TicketCreateRequest(BaseModel):
    """Schema for creating a new ticket."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brief title describing the ticket",
        examples=["Bug in login system"],
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Detailed description of the ticket",
        examples=["Users cannot log in with valid credentials after recent update"],
    )
    reporter: str = Field(
        ...,
        min_length=1,
        description="Username or email of the person creating the ticket",
        examples=["user@example.com"],
    )
    priority: TicketPriority = Field(
        default=TicketPriority.LOW,
        description="Priority level for the ticket",
    )
    assignee: str | None = Field(
        default=None,
        description="Optional username or email to assign the ticket to",
        examples=["developer@example.com"],
    )


class TicketUpdateRequest(BaseModel):
    """Schema for updating an existing ticket. All fields are optional."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="New title for the ticket",
    )
    description: str | None = Field(
        default=None,
        min_length=1,
        description="New description for the ticket",
    )
    status: TicketStatus | None = Field(
        default=None,
        description="New status for the ticket",
    )
    priority: TicketPriority | None = Field(
        default=None,
        description="New priority level for the ticket",
    )
    assignee: str | None = Field(
        default=None,
        description="New assignee for the ticket",
    )


class CommentCreateRequest(BaseModel):
    """Schema for adding a comment to a ticket."""

    author: str = Field(
        ...,
        min_length=1,
        description="Username or email of the comment author",
        examples=["developer@example.com"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Comment text content",
        examples=["I've started investigating this issue"],
    )


# ============================================================================
# RESPONSE MODELS - Used for outgoing data serialization
# ============================================================================


class CommentResponse(BaseModel):
    """Schema for a comment in API responses and ticket responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier for the comment")
    ticket_id: UUID = Field(description="ID of the ticket this comment belongs to")
    author: str = Field(description="Author of the comment")
    content: str = Field(description="Comment content")
    created_at: datetime = Field(description="When the comment was created")


class TicketResponse(BaseModel):
    """Schema for a ticket in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Unique identifier for the ticket")
    title: str = Field(description="Ticket title")
    description: str = Field(description="Ticket description")
    status: TicketStatus = Field(description="Current status of the ticket")
    priority: TicketPriority = Field(description="Priority level of the ticket")
    reporter: str = Field(description="Person who created the ticket")
    assignee: str | None = Field(description="Person assigned to the ticket")
    created_at: datetime = Field(description="When the ticket was created")
    updated_at: datetime = Field(description="When the ticket was last updated")
    comments: list[CommentResponse] = Field(
        default_factory=list,
        description="Comments on the ticket",
    )


class TicketListResponse(BaseModel):
    """Schema for paginated list of tickets."""

    tickets: list[TicketResponse] = Field(description="List of tickets")
    total: int = Field(description="Total number of tickets returned")
    limit: int = Field(description="Maximum number of tickets requested")
    offset: int = Field(description="Number of tickets skipped")


class HealthResponse(BaseModel):
    """Schema for health check endpoint response."""

    status: str = Field(description="Health status of the service")
    service: str = Field(description="Service name")
    version: str = Field(description="Service version")


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    detail: str = Field(description="Error message")
    error_code: str | None = Field(
        default=None,
        description="Optional error code for programmatic handling",
    )
