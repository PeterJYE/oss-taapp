# DESIGN — Homework 1 changes

This document explains the architecture and design of the service-based components added for Homework 1. It documents how the FastAPI service, the auto-generated HTTP client, and the adapter (shim) work together so that existing code written against the original library continues to work unchanged.

## Architecture overview

- Goal: turn the library-based Gmail implementation into a network service so multiple programs can share a single, long-running connection to the mail provider. ##(CREATE A SERVICE)
- Three new bridges added:
  - FastAPI service (backend) — `src/mail_client_service/src/main.py`
  - Auto-generated HTTP client — `src/generated_client/mail_client_service_client`, script that grabs openAPI spec from fastAPI service to autogenerate client (WIP)
  - Adapter / Service shim — `src/adapter/service_client_adapter.py` which implements the original `mail_client_api.Client` interface but forwards requests to the generated HTTP client.
<!-- 
callers swap in the adapter instead of the concrete Gmail library and call the same methods. -->

## Components

<!-- - mail_client_api (existing): the interface part of our project. It defines an abstract base class that specifies what the mail client should do (get_messages, get_message, etc.)
- gmail_client_impl (existing): original concrete Gmail implementation that knows how to talk to Gmail's API -->

- mail_client_service (new): a fastAPI web service that exposes the email client functionality over HTTP. This means that instead of calling python functions directly, other programs can interact with our email client by sending HTTP Requests to specific endpoints provided by our fastAPI service
  - `src/mail_client_service/src/main.py` — defines endpoints:
    - `GET /messages` — returns a list of message summaries
    - `GET /messages/{message_id}` — returns full message detail
    - `POST /messages/{message_id}/mark-as-read` — marks message as read
    - `DELETE /messages/{message_id}` — deletes message
  - The service delegates all logic and auth to the existing implementation.

- generated_client (new): an auto-generated OpenAPI client that provides a client for the FastAPI service endpoints. The adapter uses this client.

- adapter.ServiceClientAdapter (new): The adapter acts as a bridge, making the service-based client behave exactly like the original client. This way, user code doesn't have to change.

## Request flow

Example: consumer code calls `client.get_message('m123')` where `client` is a `ServiceClientAdapter` instance.

1. Consumer calls `ServiceClientAdapter.get_message('m123')`.
2. The adapter uses the generated client and receives a JSON response parsed into `MessageDetail` model.
3. Adapter wraps the returned model in `ServiceMessage` and returns it to the caller.
4. An HTTP GET request is sent to the FastAPI service endpoint `GET /messages/{message_id}`.
5. FastAPI's `get_message_detail` endpoint uses the dependency `get_client_dep()` to obtain an instance of gmail client
6. The service calls `gmail_client_impl.GmailClient.get_message(message_id)` and returns the result as JSON.
7. The adapter returns the wrapped `ServiceMessage` to the original caller.

Diagram (linear):
user code → adapter (ServiceClientAdapter) → generated client (HTTP) → FastAPI service (/messages/...) → gmail_client_impl (local) → FastAPI → generated client → adapter → user code

## Sample API responses

- GET /messages (200):
```json
[ 
  {"id": "m1", "subject": "Subject 1"},
  {"id": "m2", "subject": "Subject 2"}
]
```
- GET /messages/m1 (200):
```json
{
  "id": "m1",
  "from_": "alice@example.com",
  "to": "me@example.com",
  "date": "2025-01-01T00:00:00Z",
  "subject": "Subject 1",
  "body": "Hello from dummy"
}
```
- POST /messages/m1/mark-as-read:
```json
{ "ok": true, "message": "Message 'm1' marked as read" }
```
- DELETE /messages/m1:
```json
{ "ok": true, "message": "Message 'm1' deleted successfully" }
```

## API Design
Endpoints:

- GET /messages
  - Query params: `limit` (int, default 10)
  - Response: JSON array of `{ id, subject? }`

- GET /messages/{message_id}
  - Response: MessageDetail JSON: `{ id, from_, to, date, subject, body }`

- POST /messages/{message_id}/mark-as-read
  - Response: `{ ok: bool, message?: str }`

- DELETE /messages/{message_id}
  - Response: `{ ok: bool, message?: str }`

Error handling:
- The fastAPI service converts error from our backend code int ostandard HTTP error responses
- This helps clients know what's wrong, and the goal is to make error responses clear 
- 
- Service maps internal exceptions to HTTP errors using FastAPI's `HTTPException`:
  - If `get_client_dep()` fails to initialize the client: 500 Internal Server Error (service-side init failure).
  - If `client.get_message()` raises an exception while fetching a specific message: 404 Not Found (message not found or cannot be retrieved).
  - If an action returns `False` (like delete or mark-as-read): 400 Bad Request with an explanatory detail.
  - Unexpected exceptions while iterating / processing messages: 500 Internal Server Error.

## The Adapter pattern

Why it's needed: 
- The auto-generated client makes it easy to call the FastAPI service over HTTP, but its methods and data models are not the same as the original
- You can't use the generated client directly without changing the code to match its API
- Adapter helps solve this by providing the same interface as the original client making it so we don't have to change our code


How it works (example):
<!-- NEHA CAN U DO THIS PLEASE -->

## Testing strategy

What we tested:

- Integration test that verifies adapter → service → client wiring using a test double (`DummyGmailClient`) injected into the FastAPI app. 
- E2E tests that execute the `main.py` script in both local-credentials and CI env-var modes

Test types and rationale:

- Unit tests: should test small functions in isolation 
- Integration tests: we added `test_adapter_service_integration` to ensure the adapter implements the interface and that HTTP → service → implementation flow works. This test uses `fastapi.TestClient` so no network is required.
- E2E tests: `tests/e2e/test_main_application.py` runs `main.py` as a subprocess and verifies full, real authentication flows when credentials are available.

Mocking strategy

- For our integration testing, we injected a `DummyGmailClient` using FastAPI (`mail_app.dependency_overrides[get_client_dep] = lambda: dummy`). This helped make the tests fast, more easily predictable, and not dependant on external services
- For E2E tests we run the actual `gmail_client_impl` (real credentials required) — these tests are gated using pytest markers (`local_credentials`) so CI does not run them unless credentials are provided.

Interface compliance:

- The adapter class `ServiceClientAdapter` is wsritten to inherit from the Client interfance, so it must implement all the required methods
- When it returns messages it wraps them in ServiceMessage objects that match the expected `Message` attributes and methods
- Wrote an integration test that creates an instance of the ServiceClientAdapter, calls all the main methods, and checks that the results have the correct structure
- This proves that the adapter is a true replacement for the original client, so the user code doesn't break if anything doesn't match
