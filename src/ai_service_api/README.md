# AI Service API

## Overview
`ai_service_api` defines the `AIClient` abstract base class that every AI service implementation must implement. The package contains the abstraction, a factory hook, and no concrete logic.

## Purpose
- Document the operations available to consumers.
- Provide a single factory (`get_client`) that implementations can override.
- Keep response and conversation dependencies explicit through the `ai_service_api.response` module.

## Architecture

### Component Design
The package exposes one abstract base class focused on AI operations—creating responses and managing conversations. It depends only on the `Response` and `Conversation` abstractions.

### API Integration
```python
from ai_service_api import AIClient, get_client
from ai_service_api.response import Response

client: AIClient = get_client()
response: Response = client.generate_response(["Hello, how are you?"])
print(response.content)
```

### Dependency Injection
Implementation packages (for example `openai_client_impl`) replace the factory at import time:
```python
import openai_client_impl  # rebinds ai_service_api.get_client

from ai_service_api import get_client
client = get_client(interactive=False)
```

## API Reference

### AIClient Abstract Base Class
```python
class AIClient(ABC):
    ...
```

#### Methods
- `generate_response(messages: list[str], *, conversation_id: str | None = None) -> Response`: Generate a model response given messages and optional conversation ID.
- `create_conversation() -> str`: Create a new conversation and return its ID.
- `get_conversation(conversation_id: str) -> Conversation`: Retrieve a conversation by its ID.
- `delete_conversation(conversation_id: str) -> bool`: Delete a conversation and all its messages.

### Response Abstract Base Class
Represents an AI-generated response with properties:
- `content (str)`: The text content of the AI response.
- `tokens_used (int)`: The number of tokens consumed.
- `conversation_id (str | None)`: The conversation ID this response belongs to.

### Conversation Abstract Base Class
Represents a conversation with properties:
- `id (str)`: The unique conversation identifier.
- `messages (list[tuple[str, str]])`: All messages as (role, content) tuples.
- `created_at (str)`: When the conversation was created.

Messages are stored as tuples of (role, content) where role is typically 'user' or 'assistant' (or 'system' for system prompts). This allows the implementation to properly format messages for OpenAI's Chat Completions API.

### Factory Function
`get_client(*, interactive: bool = False) -> AIClient`: Returns the bound implementation or raises `NotImplementedError` if none registered.

## Usage Examples

### Basic Response Creation
```python
from ai_service_api import get_client

client = get_client(interactive=False)
response = client.generate_response(["Hello, how can you help me today?"])
print(f"Response: {response.content}")
print(f"Tokens used: {response.tokens_used}")
```

### Conversation Management
```python
from ai_service_api import get_client

client = get_client()

# Create a new conversation
conv_id = client.create_conversation()
print(f"Conversation ID: {conv_id}")

# Send messages in the conversation
response = client.generate_response(["Hello!"], conversation_id=conv_id)
print(response.content)

# Retrieve conversation
conversation = client.get_conversation(conv_id)
print(f"Messages: {conversation.messages}")
# Output: [("user", "Hello!")]

# Access individual messages
for role, content in conversation.messages:
    print(f"{role}: {content}")

# Delete the conversation
client.delete_conversation(conv_id)
```

## Implementation Checklist
1. Implement every method in the abstract base class.
2. Return objects compatible with `ai_service_api.response.Response` and `Conversation`.
3. Publish a factory (`get_client_impl`) and assign it to `ai_service_api.get_client`.
4. Honour the `interactive` flag (prompting only when `True`).

## Testing
```bash
uv run pytest src/ai_service_api/tests/ -q
uv run pytest src/ai_service_api/tests/ --cov=src/ai_service_api --cov-report=term-missing
```

