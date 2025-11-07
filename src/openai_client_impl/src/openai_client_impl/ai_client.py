"""AI client implementation that implements the AIClient interface."""

import json
import uuid
from datetime import UTC, datetime

try:  # pragma: no cover - optional dependency handling
    from openai import (  # type: ignore[import-not-found]
        APIConnectionError,
        APIError,
        AuthenticationError,
        BadRequestError,
        OpenAI,
        RateLimitError,
    )
except Exception:  # pragma: no cover - provide lightweight fallbacks  # noqa: BLE001
    class _DummyError(Exception):
        """Fallback OpenAI error base when openai package isn't installed."""


    APIConnectionError = _DummyError  # type: ignore[assignment]
    APIError = _DummyError  # type: ignore[assignment]
    AuthenticationError = _DummyError  # type: ignore[assignment]
    BadRequestError = _DummyError  # type: ignore[assignment]
    RateLimitError = _DummyError  # type: ignore[assignment]

    class OpenAIFallback:  # type: ignore[override]
        """Minimal fallback that raises informative errors when used."""

        def __init__(self, api_key: str | None = None) -> None:  # noqa: D107
            self.api_key = api_key

        class Chat:  # noqa: D106
            class Completions:  # noqa: D106
                @staticmethod
                def create(*_args: object, **_kwargs: object) -> None:  # noqa: D102
                    msg = "openai package not installed; AI operations unavailable"
                    raise RuntimeError(msg)

            completions = Completions()

        chat = Chat()

from openai_client_impl.errors import MissingOpenAIKeyError
from openai_client_impl.response import Conversation, Response, get_conversation, get_response
from openai_client_impl.storage import (
    delete_conversation,
    get_conversation_data,
    get_openai_key,
    save_conversation,
)

DEFAULT_MODEL = "gpt-4o-mini"


class AIClientImpl:
    """Concrete implementation of AIClient using OpenAI API."""

    def __init__(self, subject: str) -> None:
        """Initialize AI client for a specific user/subject.

        Args:
            subject: User identifier for API key lookup and conversation scoping.

        """
        self.subject = subject
        self._sdk = self._get_sdk()

    def _get_sdk(self) -> OpenAI:
        """Get OpenAI SDK client for the user.

        Returns:
            OpenAI client instance.

        Raises:
            MissingOpenAIKeyError: If user hasn't set an API key.

        """
        key = get_openai_key(self.subject)
        if not key:
            error_msg = "OpenAI API key is not set for this user. Set it via the service."
            raise MissingOpenAIKeyError(error_msg)
        return OpenAI(api_key=key)

    def generate_response(  # noqa: C901, PLR0912 - acceptable complexity given explicit error handling paths
        self,
        messages: list[str],
        *,
        conversation_id: str | None = None,
    ) -> Response:
        """Generate a model response given messages and optional conversation ID.

        Args:
            messages: A list of message strings in the conversation.
            conversation_id: Optional conversation ID to continue existing
                conversation. If None, creates a new conversation.

        Returns:
            An AI-generated response.

        Raises:
            ValueError: If messages list is empty.
            RuntimeError: If the AI service fails to process the request.

        """
        if not messages:
            error_msg = "Messages list cannot be empty"
            raise ValueError(error_msg)

        openai_messages: list[dict[str, str]] = [{"role": "user", "content": msg} for msg in messages]

        if conversation_id:
            conv_data = get_conversation_data(conversation_id)
            if conv_data:
                _, _, messages_json = conv_data
                existing_messages = json.loads(messages_json)
                openai_messages = existing_messages + openai_messages
        try:
            resp = self._sdk.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=openai_messages,  # type: ignore[arg-type]
            )
        except AuthenticationError:
            # Do not expose raw exception details (could leak secrets)
            error_msg = "OpenAI authentication failed. Please set a valid API key."
            raise RuntimeError(error_msg) from None
        except RateLimitError:
            error_msg = "OpenAI rate limit exceeded. Please try again later."
            raise RuntimeError(error_msg) from None
        except APIConnectionError:
            error_msg = "Network error communicating with OpenAI API."
            raise RuntimeError(error_msg) from None
        except BadRequestError:
            error_msg = "Invalid request sent to OpenAI API."
            raise RuntimeError(error_msg) from None
        except APIError:
            error_msg = "OpenAI API error occurred while processing the request."
            raise RuntimeError(error_msg) from None
        except Exception:  # noqa: BLE001 - final safety net with generic message to avoid leaking details
            # Fallback: keep message generic to avoid leaking internal details
            error_msg = "AI service failed to process request."
            raise RuntimeError(error_msg) from None

        content = resp.choices[0].message.content or ""
        tokens_used = resp.usage.total_tokens if resp.usage else 0

        if conversation_id:
            conv_data = get_conversation_data(conversation_id)
            if conv_data:
                _, created_at, _ = conv_data
            else:
                created_at = datetime.now(UTC).isoformat()

            updated_messages = [*openai_messages, {"role": "assistant", "content": content}]
            save_conversation(
                conv_id=conversation_id,
                subject=self.subject,
                created_at=created_at,
                messages_json=json.dumps(updated_messages),
            )
        else:
            conversation_id = self.create_conversation()
            created_at = datetime.now(UTC).isoformat()
            updated_messages = [*openai_messages, {"role": "assistant", "content": content}]
            save_conversation(
                conv_id=conversation_id,
                subject=self.subject,
                created_at=created_at,
                messages_json=json.dumps(updated_messages),
            )

        return get_response(content, tokens_used, conversation_id)

    def create_conversation(self) -> str:
        """Create a new conversation and return its ID.

        Returns:
            The conversation ID of the newly created conversation.

        Raises:
            RuntimeError: If the conversation could not be created.

        """
        try:
            conv_id = str(uuid.uuid4())
            created_at = datetime.now(UTC).isoformat()
            save_conversation(
                conv_id=conv_id,
                subject=self.subject,
                created_at=created_at,
                messages_json=json.dumps([]),
            )
        except Exception as e:
            error_msg = f"Could not create conversation: {e}"
            raise RuntimeError(error_msg) from e
        else:
            return conv_id

    def get_conversation(self, conversation_id: str) -> Conversation:
        """Retrieve a conversation by its ID.

        Args:
            conversation_id: The unique identifier of the conversation.

        Returns:
            The conversation object.

        Raises:
            ValueError: If conversation_id is invalid or not found.

        """
        conv_data = get_conversation_data(conversation_id)
        if not conv_data:
            error_msg = f"Conversation not found: {conversation_id}"
            raise ValueError(error_msg)

        _, created_at, messages_json = conv_data
        try:
            messages_list = json.loads(messages_json)
            messages = [(msg["role"], msg["content"]) for msg in messages_list]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            error_msg = f"Invalid conversation data: {e}"
            raise ValueError(error_msg) from e

        return get_conversation(conversation_id, messages, created_at)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: The unique identifier of the conversation.

        Returns:
            True if successfully deleted, False otherwise.

        Raises:
            ValueError: If conversation_id is invalid or not found.

        """
        deleted = delete_conversation(conversation_id)
        if not deleted:
            error_msg = f"Conversation not found: {conversation_id}"
            raise ValueError(error_msg)
        return deleted
