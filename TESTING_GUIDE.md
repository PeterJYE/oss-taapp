# Testing Guide for `/ai/generate_response` Endpoint

## Automated Tests

Run the unit tests using pytest:

```bash
# Run all tests
pytest src/openai_client_service/tests/test_ai_routes.py

# Run only the generate_response tests
pytest src/openai_client_service/tests/test_ai_routes.py::test_generate_response_success
pytest src/openai_client_service/tests/test_ai_routes.py::test_generate_response_with_schema
pytest src/openai_client_service/tests/test_ai_routes.py::test_generate_response_missing_api_key
pytest src/openai_client_service/tests/test_ai_routes.py::test_generate_response_handles_api_error
```

## Manual Testing

### 1. Set up your environment

Create a `.env` file in the project root (if it doesn't exist) and add your OpenAI API key:

```bash
echo "OPENAI_API_KEY=sk-your-actual-api-key-here" >> .env
```

### 2. Start the service

```bash
# From the project root
uvicorn openai_client_service.main:app --reload --port 8000
```

Or if using the main.py entry point:
```bash
python -m openai_client_service.main
```

### 3. Test with curl

#### Basic request (returns string response):

```bash
curl -X POST "http://localhost:8000/ai/generate_response" \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Hello, how are you?",
    "system_prompt": "You are a helpful assistant."
  }'
```

Expected response:
```json
"Hello! I'm doing well, thank you for asking. How can I help you today?"
```

#### Request with structured output (returns JSON dict):

```bash
curl -X POST "http://localhost:8000/ai/generate_response" \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "What is the weather like?",
    "system_prompt": "You are a weather assistant. Respond with structured data.",
    "response_schema": {
      "type": "object",
      "properties": {
        "location": {"type": "string"},
        "temperature": {"type": "number"},
        "condition": {"type": "string"}
      },
      "required": ["location", "temperature", "condition"]
    }
  }'
```

Expected response:
```json
{
  "location": "New York",
  "temperature": 72,
  "condition": "sunny"
}
```

### 4. Test with Python requests

```python
import requests

# Basic request
response = requests.post(
    "http://localhost:8000/ai/generate_response",
    json={
        "user_input": "Hello!",
        "system_prompt": "You are a helpful assistant."
    }
)
print(response.json())  # String response

# Structured output request
response = requests.post(
    "http://localhost:8000/ai/generate_response",
    json={
        "user_input": "What is 2+2?",
        "system_prompt": "You are a math tutor.",
        "response_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "number"},
                "explanation": {"type": "string"}
            },
            "required": ["answer", "explanation"]
        }
    }
)
print(response.json())  # Dict response
```

### 5. Test error cases

#### Missing API key:

```bash
# Temporarily unset the environment variable
unset OPENAI_API_KEY

# Or remove it from .env and restart the server
curl -X POST "http://localhost:8000/ai/generate_response" \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Hello",
    "system_prompt": "You are a helpful assistant."
  }'
```

Expected response (400 Bad Request):
```json
{
  "detail": "OPENAI_API_KEY environment variable is not set. Please set it in your .env file."
}
```

### 6. View API documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

You can test the endpoint directly from the Swagger UI interface.

## Test Coverage

The automated tests cover:
- ✅ Successful response generation (string output)
- ✅ Structured output with JSON schema
- ✅ Missing API key error handling
- ✅ API error handling (rate limits, network issues, etc.)

