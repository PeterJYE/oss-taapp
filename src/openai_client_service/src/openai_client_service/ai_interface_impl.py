"""Implementation of AIInterface that reads API key from environment variables."""

import json
import os
from typing import Any

from openai import OpenAI

from ai_api import AIInterface  # type: ignore[attr-defined]

DEFAULT_MODEL = "gpt-4o-mini"


class EnvAIImplementation(AIInterface):
    """Implementation of AIInterface that uses OpenAI API key from environment variables."""

    def __init__(self) -> None:
        """Initialize the AI implementation with API key from environment."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            error_msg = "OPENAI_API_KEY environment variable is not set. Please set it in your .env file."
            raise ValueError(error_msg)
        self._client = OpenAI(api_key=api_key)

    def _prepare_schema(self, response_schema: dict[str, Any]) -> dict[str, Any]:
        """Prepare schema for OpenAI structured output.

        Args:
            response_schema: The user-provided JSON schema

        Returns:
            Schema with additionalProperties and required fields added

        """
        schema_with_additional_props = dict(response_schema)
        if "additionalProperties" not in schema_with_additional_props:
            schema_with_additional_props["additionalProperties"] = False

        # All properties in the response schema are assumed to be required
        if "properties" in schema_with_additional_props:
            all_properties = list(schema_with_additional_props["properties"].keys())
            schema_with_additional_props["required"] = all_properties

        return schema_with_additional_props

    def _parse_response(self, content: str, response_schema: dict[str, Any] | None) -> str | dict[str, Any]:
        """Parse the AI response based on whether schema was provided.

        Args:
            content: The response content from OpenAI
            response_schema: Optional schema that was used

        Returns:
            Parsed response as string or dict

        """
        if response_schema is not None:
            try:
                parsed_raw = json.loads(content)
                if not isinstance(parsed_raw, dict):
                    error_msg = "Structured response must be a dictionary"
                    raise TypeError(error_msg)
                parsed: dict[str, Any] = parsed_raw
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse structured response as JSON: {e}"
                raise RuntimeError(error_msg) from e
            else:
                return parsed
        else:
            return str(content)

    def generate_response(
        self,
        user_input: str,
        system_prompt: str,
        response_schema: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        """Generate a response from the AI.

        :param user_input: The text provided by the chat user.
        :param system_prompt: The instruction set (e.g., "You are a helpful assistant...").
        :param response_schema: An optional JSON schema (dict).
                                If provided, the AI must return a structured Dict matching this schema.
                                If None, the AI returns a conversational String.

        :return: A string (conversation) or a Dict (structured action data).
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

        # Prepare the completion parameters
        completion_params: dict[str, Any] = {
            "model": DEFAULT_MODEL,
            "messages": messages,  # type: ignore[arg-type]
        }

        # If response_schema is provided, use structured output with JSON schema
        if response_schema is not None:
            prepared_schema = self._prepare_schema(response_schema)
            completion_params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": True,
                    "schema": prepared_schema,
                },
            }

        def _raise_empty_response() -> None:
            error_msg = "AI service returned empty response"
            raise RuntimeError(error_msg)

        try:
            response = self._client.chat.completions.create(**completion_params)
            content = response.choices[0].message.content

            if content is None:
                _raise_empty_response()
            return self._parse_response(content, response_schema)

        except RuntimeError:
            # Re-raise RuntimeError as-is
            raise
        except Exception as e:
            error_msg = f"AI service failed to process request: {e}"
            raise RuntimeError(error_msg) from e
