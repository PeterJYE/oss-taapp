# OpenAI Client Service

A FastAPI-based service that provides a secure, multi-user interface to OpenAI's API with conversation management and encrypted API key storage.

## Architecture

This project implements a clean architecture with the following components:

- **`ai_service_api`**: Abstract interfaces (`AIClient`, `Response`, `Conversation`)
- **`openai_client_impl`**: Concrete OpenAI implementation with secure storage
- **`openai_client_service`**: FastAPI service exposing the interface as HTTP endpoints
- **`openai_client_service_api_client`**: Auto-generated client library

## Features

- 🔐 **Secure API Key Storage**: Encrypted storage using Fernet encryption
- 👥 **Multi-User Support**: Per-user API keys and conversation isolation
- 💬 **Conversation Management**: Create, retrieve, and delete conversations
- 🤖 **AI Response Generation**: Generate responses using OpenAI's API
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
- `POST /auth/set-openai-key` - Store OpenAI API key for a user

### AI Operations
- `POST /ai/generate-response` - Generate AI response
- `POST /ai/conversations` - Create new conversation
- `GET /ai/conversations/{conversation_id}` - Get conversation
- `DELETE /ai/conversations/{conversation_id}` - Delete conversation

### System
- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation
- `GET /openapi.json` - OpenAPI specification

## Usage Examples

### 1. Set API Key
```bash
curl -X POST http://localhost:8000/auth/set-openai-key \
  -H "Content-Type: application/json" \
  -d '{"subject": "user123", "api_key": "sk-your-openai-key"}'
```

### 2. Create Conversation
```bash
curl -X POST http://localhost:8000/ai/conversations \
  -H "X-Subject: user123"
```

### 3. Generate Response
```bash
curl -X POST http://localhost:8000/ai/generate-response \
  -H "Content-Type: application/json" \
  -H "X-Subject: user123" \
  -d '{
    "messages": ["Hello, how are you?"],
    "conversation_id": "your-conversation-id"
  }'
```

### 4. Get Conversation
```bash
curl -X GET http://localhost:8000/ai/conversations/your-conversation-id \
  -H "X-Subject: user123"
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

## Development

### Project Structure
```
oss-taapp/
├── src/
│   ├── ai_service_api/          # Abstract interfaces
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

## Security

- API keys are encrypted using Fernet encryption
- Per-user isolation ensures data privacy
- No API keys are logged or exposed in responses
- Database uses encrypted storage for sensitive data
