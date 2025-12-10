# Ticket Service

FastAPI REST service exposing ticket operations over HTTP with cookie-based authentication.

## Purpose

- Wraps `TicketImpl` as HTTP endpoints
- Cookie-based session authentication
- OAuth 2.0 integration for Jira
- OpenAPI/Swagger documentation
- Pydantic request/response validation

## Installation

```bash
uv add ticket-service
```

## Running

```bash
# Development
uv run uvicorn ticket_service.main:app --reload

# Production
uv run uvicorn ticket_service.main:app --host 0.0.0.0 --port 8000
```

Visit:
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Endpoints

### Authentication
- `GET /api/v1/auth/login` - Start OAuth flow
- `GET /api/v1/auth/callback` - OAuth callback
- `GET /api/v1/auth/status` - Check auth status
- `POST /api/v1/auth/logout` - Logout

### Tickets
- `POST /api/v1/tickets` - Create ticket
- `GET /api/v1/tickets/{id}` - Get ticket
- `GET /api/v1/tickets` - List tickets (with filters)
- `PATCH /api/v1/tickets/{id}` - Update ticket
- `DELETE /api/v1/tickets/{id}` - Delete ticket

### Comments
- `POST /api/v1/tickets/{id}/comments` - Add comment
- `GET /api/v1/tickets/{id}/comments` - Get comments

### Health
- `GET /health` - Service health

## Authentication

Uses cookie-based sessions:
1. Visit `/api/v1/auth/login`
2. Complete OAuth flow
3. Cookie automatically set
4. All subsequent requests authenticated

For programmatic access, use `X-User-ID` and `X-Project-Key` headers.

## Configuration

```bash
OAUTH_CLIENT_ID="your-client-id"
OAUTH_CLIENT_SECRET="your-secret"
OAUTH_REDIRECT_URI="http://localhost:8000/api/v1/auth/callback"
JIRA_CLOUD_ID="your-cloud-id"
CORS_ORIGINS="http://localhost:3000"
```

## Error Responses

- `200/201` - Success
- `400` - Invalid input
- `401` - Not authenticated
- `404` - Not found
- `500` - Server error

## Testing

```bash
uv run pytest src/ticket_service/tests/ -v
```

**Coverage:** 90%+ (25+ tests)

Tests use `TestClient` with mocked `TicketImpl`.

## Deployment

See `VERCEL_DEPLOYMENT.md` or `render.yaml` for deployment guides.
