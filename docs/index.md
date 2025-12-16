# Welcome to OSS TA App

A multi-service application integrating Chat (Slack), AI (OpenAI), and Ticket (JIRA) using shared interfaces.

## Architecture Overview

```
User Message (Slack) → AI Service (OpenAI) → Ticket Service (JIRA) → Response (Slack)
```

This project uses a component-based architecture with a clear separation between interface and implementation, allowing for flexible service integration and testing.

## Services

- **Chat Service**: Slack integration for receiving and sending messages
- **AI Service**: OpenAI integration for natural language processing and ticket operation extraction
- **Ticket Service**: JIRA integration for ticket management (create, read, update, delete)
- **Integration Service**: Orchestrates the flow between all services

This documentation site provides an overview of the project's architecture, API contracts, and usage guidelines.
