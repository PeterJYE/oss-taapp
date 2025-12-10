"""Production-like integration service using only shared interfaces.

This service polls for messages from the chat interface and processes them:
1. Polls for new messages from Chat service (Slack)
2. For each new message → AI service (converts to structured JSON)
3. AI response → Ticket service (executes operation)
4. Sends response back to user via Chat service

All using only the shared interfaces: ChatInterface, AIInterface, TicketInterface

Environment Variables:
    CHAT_SERVICE_BASE_URL: Slack API base URL (default: https://slack.com/api)
    CHAT_SERVICE_TOKEN: Slack user token
    CHAT_CHANNEL_ID: Channel ID to monitor (default: C123456)
    AI_SERVICE_BASE_URL: OpenAI service URL (default: http://localhost:8000)
    TICKET_SERVICE_USER_ID: JIRA user ID for authentication
    JIRA_PROJECT_KEY: JIRA project key
    JIRA_REPORTER_EMAIL: Default reporter email for tickets
"""

import os
import sys
import time
from logging import getLogger

from chat_api.chat_impl.src.slack_impl import SlackClient  # type: ignore[attr-defined]
from ticket_api.ticket_impl.src.ticket_impl import TicketImpl  # type: ignore[attr-defined]

from ai_api import AIInterface  # type: ignore[attr-defined]
from chat_api import ChatAdapter, ChatInterface  # type: ignore[attr-defined]
from openai_adapter import AIAdapter  # type: ignore[attr-defined]
from ticket_api import StandardizedTicketAdapter, TicketInterface, TicketStatus  # type: ignore[attr-defined]

logger = getLogger(__name__)


def get_ai_interface() -> AIInterface:
    """Get AI interface instance."""
    base_url = os.getenv("AI_SERVICE_BASE_URL", "http://localhost:8000")
    return AIAdapter(base_url=base_url)


def get_chat_interface() -> ChatInterface:
    """Get chat interface instance."""
    base_url = os.getenv("CHAT_SERVICE_BASE_URL")
    token = os.getenv("CHAT_SERVICE_TOKEN")
    slack_client = SlackClient(base_url=base_url, token=token)
    return ChatAdapter(slack_client)


def get_ticket_interface() -> TicketInterface:
    """Get ticket interface instance."""
    user_id = os.getenv("TICKET_SERVICE_USER_ID", "integration-user")
    project_key = os.getenv("JIRA_PROJECT_KEY", "TEST")
    reporter = os.getenv("JIRA_REPORTER_EMAIL", "rmp10015@nyu.edu")
    ticket_impl = TicketImpl(user_id=user_id, project_key=project_key)
    return StandardizedTicketAdapter(ticket_impl, reporter=reporter)


def process_message(  # noqa: C901, PLR0912, PLR0915
    user_input: str,
    channel_id: str,
    ai_interface: AIInterface,
    ticket_interface: TicketInterface,
    chat_interface: ChatInterface,
) -> None:
    """Process a user message: AI converts to JSON, Ticket executes, Chat responds.

    Args:
        user_input: The user's message text
        channel_id: The channel ID to send response to
        ai_interface: AI interface for converting natural language
        ticket_interface: Ticket interface for ticket operations
        chat_interface: Chat interface for sending responses

    """
    if not user_input or not user_input.strip():
        return  # Skip empty messages
    # System prompt tells LLM which TicketInterface methods are available
    system_prompt = """You are a helpful assistant that manages tickets.
Convert the user's message to JSON format for ticket operations.

Available TicketInterface methods:
- create_ticket(title, description, assignee=None) → requires: title, description
- get_ticket(ticket_id) → requires: ticket_id
- search_tickets(query=None, status=None) → status can be: open, in_progress, closed
- update_ticket(ticket_id, status=None, title=None) → requires: ticket_id
- delete_ticket(ticket_id) → requires: ticket_id. If ticket_id is not provided,
  use title parameter to search for the ticket by title (preferred) or description.

Return JSON with:
{
  "method": "create_ticket" | "get_ticket" | "search_tickets" | "update_ticket" | "delete_ticket",
  "parameters": {
    "title": "...",      // for create_ticket, update_ticket, delete_ticket
                         // (use this to search by title if ticket_id not available)
    "description": "...", // for create_ticket, delete_ticket (use this to search by description only if title not available)
    "ticket_id": "...",   // for get_ticket, update_ticket, delete_ticket (preferred if available)
    "query": "...",       // for search_tickets
    "status": "...",      // for search_tickets, update_ticket (open/in_progress/closed)
    "assignee": "..."     // for create_ticket
  }
}

For delete_ticket: If the user mentions a ticket title, extract it and put it in
the "title" parameter. The system will search for tickets matching that title."""

    # Schema that allows optional parameters based on method
    response_schema = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["create_ticket", "get_ticket", "search_tickets", "update_ticket", "delete_ticket"],
            },
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "ticket_id": {"type": "string"},
                    "query": {"type": "string"},
                    "status": {"type": "string", "enum": ["open", "in_progress", "closed"]},
                    "assignee": {"type": "string"},
                },
                "additionalProperties": False,
                "required": ["title", "description", "ticket_id", "query", "status", "assignee"],
                # All fields required by OpenAI schema, but empty strings mean "not provided"
            },
        },
        "required": ["method", "parameters"],
        "additionalProperties": False,
    }

    # Step 1: AI converts natural language to structured JSON
    ai_response = ai_interface.generate_response(
        user_input=user_input,
        system_prompt=system_prompt,
        response_schema=response_schema,
    )

    if not isinstance(ai_response, dict):
        error_msg = "AI returned non-dict response"
        logger.error("%s, got: %s", error_msg, ai_response)
        chat_interface.send_message(channel_id=channel_id, content=f"❌ Error: {error_msg}")
        return

    method = ai_response.get("method")
    params = ai_response.get("parameters", {})
    logger.info("AI Response - Method: %s, Parameters: %s", method, params)

    # Step 2: Execute the appropriate TicketInterface method
    try:
        if method == "create_ticket":
            # Extract title and description - handle empty strings
            title = params.get("title", "").strip()
            description = params.get("description", "").strip()
            if not title:
                msg = f"create_ticket requires title. Got title='{title}'"
                raise ValueError(msg)  # noqa: TRY301
            # Auto-generate description from title if not provided
            if not description:
                description = f"Ticket created for: {title}"
            logger.info("Creating ticket with title: %s, description: %s", title, description)
            assignee_val = params.get("assignee", "").strip()
            ticket = ticket_interface.create_ticket(
                title=title,
                description=description,
                assignee=assignee_val if assignee_val else None,
            )
            logger.info("✅ Ticket created! ID: %s, Title: %s, Status: %s", ticket.id, ticket.title, ticket.status)
            response = (
                f"✅ Ticket created!\n**ID**: {ticket.id}\n**Title**: {ticket.title}\n"
                f"**Status**: {ticket.status}"
            )

        elif method == "get_ticket":
            ticket_id_val = params.get("ticket_id", "").strip()
            if not ticket_id_val:
                msg = "get_ticket requires ticket_id"
                raise ValueError(msg)  # noqa: TRY301
            ticket_result = ticket_interface.get_ticket(ticket_id=ticket_id_val)
            if ticket_result is None:
                msg = f"Ticket {ticket_id_val} not found"
                raise ValueError(msg)  # noqa: TRY301
            # At this point, mypy knows ticket_result is not None
            ticket = ticket_result
            response = (
                f"📋 **{ticket.title}**\n**ID**: {ticket.id}\n**Status**: {ticket.status}\n"
                f"**Description**: {ticket.description}"
            )

        elif method == "search_tickets":
            ticket_status: TicketStatus | None = None
            status_val = params.get("status", "").strip()
            if status_val:
                ticket_status = TicketStatus(status_val)
            query_val = params.get("query", "").strip()
            tickets = ticket_interface.search_tickets(
                query=query_val if query_val else None,
                status=ticket_status,
            )
            if not tickets:
                response = "🔍 No tickets found."
            else:
                tickets_list = "\n".join(f"• **{t.id}**: {t.title} ({t.status})" for t in tickets[:10])
                response = f"🔍 Found {len(tickets)} ticket(s):\n{tickets_list}"

        elif method == "update_ticket":
            ticket_id_val = params.get("ticket_id", "").strip()
            if not ticket_id_val:
                msg = "update_ticket requires ticket_id"
                raise ValueError(msg)  # noqa: TRY301
            update_status: TicketStatus | None = None
            status_val = params.get("status", "").strip()
            if status_val:
                update_status = TicketStatus(status_val)
            title_val = params.get("title", "").strip()
            ticket = ticket_interface.update_ticket(
                ticket_id=ticket_id_val,
                status=update_status,
                title=title_val if title_val else None,
            )
            response = (
                f"✅ Ticket updated!\n**ID**: {ticket.id}\n**Title**: {ticket.title}\n"
                f"**Status**: {ticket.status}"
            )

        elif method == "delete_ticket":
            ticket_id_val = params.get("ticket_id", "").strip()

            # If no ticket_id provided, search for tickets by title (preferred) or description
            if not ticket_id_val:
                title_val = params.get("title", "").strip()
                description_val = params.get("description", "").strip()

                # Prioritize title over description
                if title_val:
                    query_val = title_val
                    search_type = "title"
                elif description_val:
                    query_val = description_val
                    search_type = "description"
                else:
                    msg = "delete_ticket requires ticket_id or a search query (title/description)"
                    raise ValueError(msg)  # noqa: TRY301

                # Search for tickets matching the query
                logger.info("Searching for tickets by %s: %s", search_type, query_val)
                search_results = ticket_interface.search_tickets(query=query_val)

                if not search_results:
                    msg = f"No tickets found matching {search_type} '{query_val}'"
                    raise ValueError(msg)  # noqa: TRY301

                if len(search_results) > 1:
                    tickets_list = "\n".join(f"• **{t.id}**: {t.title}" for t in search_results)
                    msg = (
                        f"Multiple tickets found matching {search_type} '{query_val}'. "
                        f"Please specify the ticket ID:\n{tickets_list}"
                    )
                    raise ValueError(msg)  # noqa: TRY301

                # Exactly one ticket found, use its ID
                ticket_id_val = search_results[0].id
                logger.info(
                    "Found ticket to delete by %s: %s - %s",
                    search_type,
                    ticket_id_val,
                    search_results[0].title,
                )

            success = ticket_interface.delete_ticket(ticket_id=ticket_id_val)
            response = "✅ Ticket deleted successfully!" if success else "❌ Failed to delete ticket"

        else:
            msg = f"Unknown method: {method}"
            raise ValueError(msg)  # noqa: TRY301

    except (ValueError, RuntimeError) as e:
        logger.exception("❌ Error")
        error_msg = str(e)
        response = f"❌ Error: {error_msg}"

    # Step 3: Send response back via ChatInterface
    logger.info("Sending response: %s", response)
    chat_interface.send_message(channel_id=channel_id, content=response)


def main() -> None:  # noqa: C901
    """Run the production-like integration flow.

    Polls for messages from the chat interface and processes them.
    """
    # Initialize interfaces
    ai_interface = get_ai_interface()
    chat_interface = get_chat_interface()
    ticket_interface = get_ticket_interface()

    # Get channel ID from environment or command line argument
    channel_id = os.getenv("CHAT_CHANNEL_ID")

    # Allow channel ID to be passed as command line argument for testing
    if len(sys.argv) > 1:
        channel_id = sys.argv[1]
        logger.info("Using channel ID from command line: %s", channel_id)
    elif not channel_id:
        sys.exit(1)

    # Track processed message IDs to avoid duplicates
    processed_message_ids: set[str] = set()


    # Production-like polling loop
    while True:
        try:
            # Poll for new messages from the chat interface
            messages = chat_interface.get_messages(channel_id=channel_id, limit=10)

            # Process new messages (in reverse order to process oldest first)
            for message in reversed(messages):
                message_id = message.id

                # Skip if we've already processed this message
                if message_id in processed_message_ids:
                    continue

                # Extract user input from message
                user_input = message.content.strip()

                # Skip empty messages
                if not user_input:
                    processed_message_ids.add(message_id)
                    continue

                # Skip system messages (e.g., "has joined the channel")
                if "has joined the channel" in user_input or "has left the channel" in user_input:
                    processed_message_ids.add(message_id)
                    continue

                # Skip messages that look like bot responses (contain emoji patterns or response markers)
                # Convert to lowercase for case-insensitive matching
                user_input_lower = user_input.lower()

                bot_response_patterns = [
                    ":mag:",  # Search emoji
                    ":white_check_mark:",  # Success emoji
                    ":clipboard:",  # Clipboard emoji
                    ":x:",  # Error emoji
                    "**id**:",  # Response format marker (lowercase)
                    "**title**:",  # Response format marker (lowercase)
                    "**status**:",  # Response format marker (lowercase)
                    "**description**:",  # Response format marker (lowercase)
                    "no tickets found",  # Bot response text (lowercase)
                    "ticket created!",  # Bot response text (lowercase)
                    "ticket deleted",  # Bot response text (lowercase)
                    "ticket updated!",  # Bot response text (lowercase)
                    "error:",  # Error messages (lowercase)
                    "failed to",  # Error messages (lowercase)
                    "client error",  # Error messages (lowercase)
                    "httpstatuserror",  # Error messages (lowercase)
                    "for more information check:",  # Error messages (lowercase)
                    "403 forbidden",  # OAuth error
                    "oauth/token",  # OAuth error URL
                ]

                if any(pattern in user_input_lower for pattern in bot_response_patterns):
                    processed_message_ids.add(message_id)
                    continue

                # Skip messages that are responses from the bot itself
                # (In production, you'd check sender_id against bot user ID)
                # For now, we rely on pattern matching above

                logger.info("[%s] New message from user: %s", message_id, user_input)
                logger.info("-" * 50)

                # Process the message through the full flow: Chat → AI → Ticket → Chat
                try:
                    process_message(
                        user_input=user_input,
                        channel_id=channel_id,
                        ai_interface=ai_interface,
                        ticket_interface=ticket_interface,
                        chat_interface=chat_interface,
                    )
                except (ValueError, RuntimeError) as e:
                    logger.exception("❌ Error processing message")
                    # Send error response back to user
                    error_msg = str(e)
                    chat_interface.send_message(
                        channel_id=channel_id,
                        content=f"❌ Error processing your request: {error_msg!s}",
                    )

                # Mark message as processed
                processed_message_ids.add(message_id)
                logger.info("")

            # Poll interval (adjust based on your needs)
            time.sleep(2)  # Poll every 2 seconds

        except KeyboardInterrupt:
            logger.info("\n%s", "=" * 50)
            logger.info("Shutting down integration service...")
            logger.info("=" * 50)
            break
        except (ValueError, RuntimeError):
            logger.exception("❌ Error in polling loop")
            time.sleep(5)  # Wait longer on error before retrying


if __name__ == "__main__":
    main()

