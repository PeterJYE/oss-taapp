# Ticket API

Abstract interface and data models for ticketing operations. This package defines the contract that all implementations must follow.

## Purpose

- Defines `TicketServiceAPI` abstract base class
- Provides domain models: `Ticket`, `Comment`
- Declares enums: `TicketStatus`, `TicketPriority`
- Custom exceptions: `ServiceError`, `TicketNotFoundError`
- Zero external dependencies

## Installation

```bash
uv add ticket-api
```

## Usage

### Implementing the Interface

```python
from ticket_api import TicketServiceAPI, Ticket, TicketPriority

class MyTicketService(TicketServiceAPI):
    async def create_ticket(self, title: str, description: str, 
                          reporter: str, priority: TicketPriority = TicketPriority.MEDIUM,
                          assignee: str | None = None) -> Ticket:
        # Your implementation
        pass
    
    # Implement other abstract methods...
```

### Using an Implementation

```python
service: TicketServiceAPI = get_service()  # Any implementation

ticket = await service.create_ticket(
    title="Bug in login",
    description="Users cannot authenticate",
    reporter="user@example.com",
    priority=TicketPriority.HIGH
)

tickets = await service.list_tickets(status=TicketStatus.OPEN, limit=50)
```

## Data Models

### Ticket
Frozen dataclass representing a ticket with id, title, description, status, priority, assignee, reporter, timestamps, and comments.

### Comment
Frozen dataclass representing a comment with id, ticket_id, author, content, and created_at.

### Enums
- `TicketStatus`: OPEN, IN_PROGRESS, RESOLVED, CLOSED
- `TicketPriority`: LOW, MEDIUM, HIGH, CRITICAL

## Interface Methods

Required methods to implement:
- `create_ticket()` - Create new ticket
- `get_ticket()` - Get by ID
- `list_tickets()` - List with filters
- `update_ticket()` - Update fields
- `delete_ticket()` - Delete ticket
- `add_comment()` - Add comment
- `get_ticket_comments()` - Get comments
- `transition_status()` - Change status
- `reassign_ticket()` - Change assignee
- `update_priority()` - Change priority
- `update_description()` - Update description

## Testing

```bash
uv run pytest src/ticket_api/tests/ -v
```

**Coverage:** 100% (22 tests)

## Design Principles

- **Immutability**: Models are frozen dataclasses
- **Type Safety**: Full type hints for all methods
- **Simplicity**: Uses stdlib dataclasses, no external dependencies
- **Extensibility**: Easy to add new implementations
