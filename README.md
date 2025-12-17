# OSS TA App - Integrated Chat-AI-Ticket System

A multi-service application integrating Chat (Slack), AI (OpenAI), and Ticket (JIRA) using shared interfaces.

```
User Message (Slack) → AI Service (OpenAI) → Ticket Service (JIRA) → Response (Slack)
```

## Quick Start

```bash
git clone https://github.com/PeterJYE/oss-taapp.git
cd oss-taapp
uv sync --all-packages
```

## Credentials Setup

Create a `.env` file with the following:

| Service | Variable | Description |
|---------|----------|-------------|
| **OpenAI** | `OPENAI_API_KEY` | API key from [platform.openai.com](https://platform.openai.com/api-keys) |
| **Slack** | `CHAT_SERVICE_BASE_URL` | `https://slack.com/api` |
| | `CHAT_SERVICE_TOKEN` | Bot OAuth token from [api.slack.com/apps](https://api.slack.com/apps) |
| | `CHAT_CHANNEL_ID` | Channel ID to monitor |
| **JIRA** | `OAUTH_CLIENT_ID` | From [developer.atlassian.com](https://developer.atlassian.com/console/myapps/) |
| | `OAUTH_CLIENT_SECRET` | Atlassian OAuth secret |
| | `OAUTH_REDIRECT_URI` | Callback URL (HTTPS required) |
| | `JIRA_CLOUD_ID` | From `https://your-domain.atlassian.net/_edge/tenant_info` |
| | `JIRA_PROJECT_KEY` | Project key (e.g., `TEST`) |
| | `TICKET_SERVICE_USER_ID` | User ID for ticket operations |
| | `DB_URL` | `sqlite:////path/to/jira_tokens.db` |

## Running the Full Stack

```bash
# Terminal 1: AI Service
uv run uvicorn openai_client_service.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Ticket Service
uv run uvicorn ticket_service.main:app --host 0.0.0.0 --port 8001

# Terminal 3: Integration (after JIRA OAuth below)
uv run python integration_main.py
```

### JIRA OAuth (Required First)
```bash
# Start ticket service, then open browser:
open "http://localhost:8001/api/v1/auth/login?user_id=YOUR_USER_ID"
# Complete Atlassian login - token saved to DB
```

## Terraform Deployment (AWS)

### 1. Store Secrets in AWS Parameter Store
Configure the following parameters in AWS SSM Parameter Store under `/oss-taapp/`:
- `OPENAI_API_KEY`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` (SecureString)
- `JIRA_CLOUD_ID`, `TICKET_SERVICE_USER_ID`, `JIRA_PROJECT_KEY`, `CHAT_CHANNEL_ID` (String)
- `CHAT_SERVICE_TOKEN` (SecureString)

### 2. Configure and Deploy
```bash
cd terraform
# Edit terraform.tfvars with repo_url, repo_branch, ssh_allowed_cidrs
terraform init && terraform apply
```

### 3. Post-Deploy: JIRA OAuth on EC2
Use ngrok for HTTPS callback, update Atlassian app callback URL, then authenticate.

## Live Deployment URLs

| Service | URL |
|---------|-----|
| AI Service | http://18.207.168.236:8000/docs |
| AI Health | http://18.207.168.236:8000/health |
| Metrics | http://18.207.168.236:8000/metrics |
| Ticket Service | http://18.207.168.236:8001/docs |
| Prometheus | http://18.207.168.236:9090 |
| Grafana | http://18.207.168.236:3000 |

## Testing

```bash
uv run pytest                              # All tests
uv run pytest src/                         # Unit tests
uv run pytest tests/integration/ -m integration  # Integration
uv run pytest tests/e2e/ -m e2e            # E2E
```

## Observability

- **Metrics**: `http://<host>:8000/metrics`
- **Health**: `http://<host>:8000/health`
- **Logs**: CloudWatch `/aws/ec2/oss-taapp`

---

# OpenAI Client Service

A FastAPI-based service that provides a secure, multi-user interface to OpenAI's API with conversation management and encrypted API key storage.

## Architecture

This project implements a clean architecture with the following components:

- **`openai_service_api`**: Abstract interfaces (`AIClient`, `Response`, `Conversation`)
- **`openai_client_impl`**: Concrete OpenAI implementation with secure storage
- **`openai_client_service`**: FastAPI service exposing the interface as HTTP endpoints
- **`openai_client_service_api_client`**: Auto-generated client library

## Features

- 🔐 **Secure API Key Storage**: Encrypted storage using Fernet encryption
- 👥 **Multi-User Support**: Per-user API keys and conversation isolation
- 💬 **Conversation Management**: Create, retrieve, and delete conversations
- 🤖 **AI Response Generation**: Generate responses using OpenAI's API
- 🛡️ **OAuth 2.0 Authentication**: Authorization Code flow with session cookies
- 📚 **Auto-Generated Client**: OpenAPI-based client library generation

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key

### Installation

1. Clone the repository:
```bash
git clone https://github.com/PeterJYE/oss-taapp.git
cd oss-taapp
```

2. Install dependencies:
```bash
uv sync
```

The service will be available at ``

### Docker

```bash
docker build -t openai-client-service .
docker run -p 8000:8000 openai-client-service
```

## API Endpoints

### Authentication
- `GET /auth/login` - Start OAuth 2.0 Authorization Code flow
- `GET /auth/callback` - OAuth 2.0 redirect URI to complete login
- `POST /auth/logout` - Clear session
- `POST /auth/set-openai-key` - Store OpenAI API key for a user

### AI Operations
- `POST /ai/generate_response` - Generate AI response
- `POST /ai/conversations` - Create new conversation
- `GET /ai/conversations/{conversation_id}` - Get conversation
- `DELETE /ai/conversations/{conversation_id}` - Delete conversation

### System
- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation
- `GET /openapi.json` - OpenAPI specification

## Usage Examples

### 1. Login via OAuth 2.0
Open a browser and complete the provider login. A `session_id` cookie will be set on success.

### 2. Set API Key
```bash
curl -X POST http://localhost:8000/auth/set-openai-key \
  -H "Content-Type: application/json" \
  --cookie "session_id=YOUR_SESSION_ID" \
  -d '{"api_key": "sk-your-openai-key"}'
```

Note: The endpoint requires authentication via session cookie. Users can only set their own API key.

### 3. Create Conversation
```bash
curl -X POST http://localhost:8000/ai/conversations \
  --cookie "session_id=YOUR_SESSION_ID"
```

### 4. Generate Response
```bash
curl -X POST http://localhost:8000/ai/generate_response \
  -H "Content-Type: application/json" \
  --cookie "session_id=YOUR_SESSION_ID" \
  -d '{
    "messages": ["Hello, how are you?"],
    "conversation_id": "your-conversation-id"
  }'
```

### 5. Get Conversation
```bash
curl -X GET http://localhost:8000/ai/conversations/your-conversation-id \
  --cookie "session_id=YOUR_SESSION_ID"
```

## Testing

### Run All Tests
```bash
uv run pytest
```

### Run Specific Test Types
```bash
# Unit tests
uv run pytest tests/unit/

# Integration tests
uv run pytest tests/integration/

# End-to-end tests
uv run pytest tests/e2e/
```

### Test Coverage
```bash
uv run pytest --cov=src --cov-report=html
```

## Client Library Generation

The service includes an auto-generated client library:

### Generate Client
```bash
# Start the service first, then:
cd src/openai_client_service_api_client
uv run python scripts/generate_client.py
```

### Use Generated Client
```python
from openai_client_service_api_client import Client

client = Client(base_url="http://localhost:8000")
response = client.ai.generate_response(
    messages=["Hello"],
    conversation_id="conv-123",
    headers={"X-Subject": "user123"}
)
```

## AI Adapter

The `openai_adapter` package provides a thin, typed adapter for calling the running service from Python applications without pulling in the generated client. It handles base URL, headers, timeouts, and offers a simple API.

### Where it lives
- Code: `src/openai_adapter/src/openai_adapter/_adapter.py`
- Tests: `src/openai_adapter/tests/test_adapter.py`




## Development

### Project Structure
```
oss-taapp/
├── src/
│   ├── openai_adapter/              # Thin typed adapter for the service
│   ├── openai_service_api/          # Abstract interfaces
│   ├── openai_client_impl/     # OpenAI implementation
│   ├── openai_client_service/  # FastAPI service
│   └── openai_client_service_api_client/  # Generated client
├── tests/                      # Test suites
├── docs/                      # Documentation
├── pyproject.toml            # Root configuration
└── Dockerfile                # Container configuration
```

### Code Quality
```bash
# Linting
uv run ruff check .

# Type checking
uv run mypy .

# Formatting
uv run ruff format .
```

### Environment Variables
- `FERNET_KEY`: Encryption key for API key storage (auto-generated if not set)
- `OPENAPI_URL`: URL for client generation (defaults to localhost:8000)
- `OAUTH_CLIENT_ID`: OAuth 2.0 client ID
- `OAUTH_CLIENT_SECRET`: OAuth 2.0 client secret (optional if using PKCE-only)
- `OAUTH_AUTH_URL`: Authorization endpoint URL
- `OAUTH_TOKEN_URL`: Token endpoint URL
- `OAUTH_USERINFO_URL`: UserInfo endpoint URL (optional, recommended for subject)
- `OAUTH_REDIRECT_URI`: Redirect URI (e.g., `http://localhost:8000/auth/callback`)
- `OAUTH_SCOPE`: Space-separated scopes (default: `openid profile email`)

## Security

- API keys are encrypted using Fernet encryption
- Per-user isolation ensures data privacy
- No API keys are logged or exposed in responses
- Database uses encrypted storage for sensitive data
