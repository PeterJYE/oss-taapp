# Contributing Guide

This guide explains the project’s structure, how its components interact, and how to develop and test code effectively.

## Architecture Overview

### Components

The base repository follows a component-based architecture centered on separation of interface and implementation. There are two major components in the system:

#### 1. `mail_client_api` - Core Interface Layer

This package defines the abstract interfaces for the mail client system.

It contains:

- `client.py`: Declares the abstract base class `Client`, defining essential operations such as connecting to mail services and sending/receiving messages.
- `message.py`: Defines the `Message` data model and related abstractions used to represent an email’s content and metadata.

This module's goal is to specify the capabilities of the system without prescribing how it must do them.

#### 2. `gmail_client_impl` - The Concrete Implementation

This package provides the implementation of the abstract classes defined above.

It contains:

- `gmail_impl.py`: Implements the `Client` interface using Gmail’s REST API. It handles authentication, message serialization, and communication with Google services.
- `message_impl.py`: Implements the `Message` class with Gmail-specific fields.

This layer depends on `mail_client_api` but not vice versa, enforcing one-way dependency flow.

#### Component Interactions

The `mail_client_api` defines the abstract contracts for how a mail client should behave, while `gmail_client_impl` provides the concrete implementation using Gmail’s API. The dependency flows one way and the implementation depends on the interface, never the other way around. The `main.py` file connects them together.

### Interface Design

Interfaces are defined as abstract base classes (ABCs), so that making changes in one module have minimal impact on the other.

**Design Justification:**
1. Each service depends only on an interface, not on a specific implementation.
2. New modules or APIs can be introduced by implementing existing interfaces without modifying the rest of the system.

### Implementation Details

The implementation of this project follows a strict interface-to-implementation pattern.  This means that each abstract interface in `mail_client_api` has a concrete class in `gmail_client_impl` that performs the actual work.

Inside `mail_client_api`, the abstract base classes (ABCs) are defined using Python’s built-in `abc` module.

For example:

```python
from abc import ABC, abstractmethod

class Client(ABC):
    @abstractmethod
    def get_message(self, message_id: str) -> Message:
        raise NotImplementedError
```

Here, `Client` defines what any mail client must be able to do. It does not know how sending or reading emails is done, that’s left to the implementation.

In `gmail_client_impl`, these abstract methods are implemented with real Gmail API logic.

Here:
1. The `GmailClient` class inherits from `MailClient`.
2. Each abstract method is implemented using the Gmail API.
3. The implementation handles authentication, message formatting, and network requests.

This structure clearly separates:

- Interface (in `mail_client_api`) → defines the expected behavior.  
- Implementation (in `gmail_client_impl`) → provides the actual behavior.

#### Python Features/Modules

The project uses several modern Python features:

1. `abc.ABC` and `abstractmethod` → to enforce interface rules.
2. `typing` → to add clarity through type hints.
3. `dataclasses` (in `message.py`) → to define simple, structured data models for messages.

#### Extra Credit

While ABCs enforce interfaces at runtime through inheritance (a subclass must explicitly implement all abstract methods), Protocols from the `typing` module use structural typing, i.e., any class with matching methods is considered valid, even without inheritance.  
ABCs provide stronger runtime safety, while Protocols offer more flexibility and are checked only by static type checkers.

### Dependency Injection
This project uses a factory override pattern to manage dependency injection, allowing flexible swapping of implementations without altering core logic.

#### How It Works

1. The API exposes a placeholder factory:
A get_client() function is defined in the mail client API as an entry point but
intentionally raises a NotImplementedError.
```python
# mail_client_api/client.py
def get_client(*, interactive: bool = False) -> Client:
    raise NotImplementedError  

```
2. A concrete implementation replaces the factory: The actual client registers its own factory by overriding the placeholder.
```python
# gmail_impl.py
def get_client_impl(*, interactive: bool = False) -> Client:
    return GmailClient(interactive=interactive)

def register() -> None:
    mail_client_api.get_client = get_client_impl  # Replace the placeholder  

```

3. Automatic registration on import
```python
# gmail_client_impl/__init__.py
register()  # Triggered when the module is imported


```

4. Application simply calls the API

```python
import gmail_client_impl
import mail_client_api

client = mail_client_api.get_client() 


```

#### What this enables:
- Contributors can swap implementations (e.g., mock clients for testing or other email providers) without changing core logic.

- Unit tests can inject mock dependencies easily.

- The system remains modular and extensible, functioning like a lightweight plugin system.

   
## Repository Structure

### Project Organization

The project follows a modular directory structure designed for clarity and scalability.

```
oss-taapp/
├── main.py
├── src/
│   ├── mail_client_api/
│   │   └── src/
│   │       └── mail_client_api/
│   │           ├── client.py
│   │           ├── message.py
│   │           └── __init__.py
│   ├── gmail_client_impl/
│   │   └── src/
│   │       └── gmail_client_impl/
│   │           ├── gmail_impl.py
│   │           ├── message_impl.py
│   │           └── __init__.py
│
├── tests/
├── docs/
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml
└── uv.lock
```

### src/

The source directory contains the core code for both abstract definitions and concrete implementations.

- **mail_client_api/**  
Defines abstract interfaces (`MailClient`, `Message`) using Python’s `abc` module.  
Contains data models that other components follow.

- **gmail_client_impl/**  
Provides the concrete implementation of the interfaces defined in `mail_client_api`.  
Implements real logic for interacting with the Gmail API.

### tests/ 
Contains all unit and integration tests for both API and implementation components.  
Ensures that every implementation correctly follows its interface and behaves as expected.

### docs/
Holds the project’s documentation, built with MkDocs and includes design and architecture guides, contributor instructions, and component-level explanations.

**main.py**  
Acts as the main entry point for the project.

### Configuration Files

The project uses `pyproject.toml` files at both the root and component levels to manage dependencies, tools, and build configurations in a modular way.  
This setup ensures that each component can be developed, tested, and packaged independently while still fitting into the overall project structure.

**Root pyproject.toml**

It is located in the main project directory (`oss-taapp/pyproject.toml`).

It defines global configuration for the entire project, including:

- Common dependencies shared across all components.
- Formatting and linting tools (e.g., Ruff, Black).
- Testing configuration for Pytest.
- Project-wide metadata such as version, license, and maintainers.

It acts as the central build file that coordinates the submodules.

**Component-Level pyproject.toml**

Each subpackage — such as `mail_client_api` and `gmail_client_impl` — has its own `pyproject.toml` inside the component folder.  
This help define component-specific settings, allowing each module to be developed as a standalone Python package.

### Package Structure

In this project, directories have been converted to packages with the help of `__init__.py` files.

In this repository, `__init__.py` files are found in two locations:

1. `src/mail_client_api/src/mail_client_api/__init__.py`
2. `src/gmail_client_impl/src/gmail_client_impl/__init__.py`

These make both the `mail_client_api` and `gmail_client_impl` directories importable as packages across the project.

The convention of keeping `__init__.py` slim means:

- Avoid placing complex logic, heavy imports, or function definitions inside it.
- Use it only to expose key modules or classes for convenience.

This approach ensures faster imports and better modularity.  
All developers should use this approach and avoid running code and exporting external libraries in `__init__.py` files.

### Import Guidelines

For this project, general rules for imports are as follows:

✅ Group imports logically.  
Follow the standard Python import order:

1. Standard library imports (e.g., `os`, `json`)
2. Third-party packages (e.g., `requests`, `googleapiclient`)
3. Local application imports (e.g., `from mail_client_api import client`)

For example:

```python
import os
import json

from googleapiclient.discovery import build
from mail_client_api.client import MailClient
```

✅ Always import modules using the full package path rather than relative paths.  
For example:

```python
from mail_client_api.client import MailClient
from gmail_client_impl.gmail_impl import GmailClient
```

**Relative vs Absolute Imports**

Relative imports (for example, `from . import client`) should be used only within the same component package to simplify internal module references. This keeps internal references concise.

❌ Avoid using relative imports across components (e.g., between `mail_client_api` and `gmail_client_impl`).  
This breaks modularity and can cause import errors when packages are installed independently.

Relative imports are currently not used in this repository.

❌ Relative imports should also be avoided in scripts like `main.py`, where packages should be imported absolutely.

## Testing Strategy

### 1. General Principles  
Contributors should view testing as a continuous part of development rather than a final step. Every test should be fast, isolated, repeatable, self-verifying, and timely—running quickly, producing consistent results, and clearly checking correctness.  
Tests must focus on behaviors instead of internal methods, using the public API to mirror real usage. They should avoid logic or unnecessary details, remaining clear and concise so anyone can understand their purpose.  
When refactoring or fixing bugs, contributors should add new tests rather than modify existing ones, ensuring the test suite reliably supports ongoing code quality and stability.

### 2. Test Organization  
- **Unit Tests** — Located under each component’s `src/<component>/tests/`. These target internal logic such as classes, functions, and behaviors in isolation, using mocks or stubs as needed.  
- **Integration Tests** — Found in `tests/integration/`. These validate how multiple components interact (for example, ensuring `gmail_client_impl` and `mail_client_api` cooperate correctly).  
- **End-to-End (E2E) Tests** — Stored in `tests/e2e/`. These simulate complete user workflows such as authentication, message retrieval, marking messages read/unread, and handling errors with real or mock APIs.

### 3. Abstraction Levels  
Tests operate across three abstraction levels:  
- **Unit Tests:** Verify individual components in isolation.  
- **Integration Tests:** Ensure components interact correctly.  
- **End-to-End Tests:** Validate full workflows from the user’s perspective to confirm that the entire system works as expected.

### 4. Code Coverage  
The project uses **pytest** with the **pytest-cov** plugin to measure how much of the codebase is covered by tests. The minimum acceptable coverage is **85%**, balancing thoroughness with development efficiency.  
- To view coverage in the terminal:  
  ```bash
  uv run pytest --cov=src --cov-report=term-missing
- To generate an HTML coverage report:
  ```bash
  uv run pytest --cov=src --cov-report=html
## Development Tools

### 1. Workspace Management  
This project uses a **uv workspace** to manage all components under one shared environment. Running `uv sync` installs every dependency defined in the root configuration.  
Contributors can use:  
- `uv run pytest` → run tests  
- `uv run ruff check .` → run static analysis  
- `uv run black .` → format code  
The root `pyproject.toml` defines shared dependencies, settings, and tool configurations, while each component’s own `pyproject.toml` lists only what that specific part needs. This setup ensures modularity, consistency, and easy environment setup.

### 2. Static Analysis and Code Formatting  
The project uses **Ruff** for static analysis and **Black** for code formatting.  
- **Ruff** checks for unused imports, style violations, and simple logic issues.  
- **Black** formats code automatically to a uniform style.  
To use them:  
``bash
uv run ruff check .
uv run black .
These tools are integrated with the uv workspace, so no separate installation is required. Consistent formatting and static analysis keep the codebase clean, readable, and reliable.

### 3.Documentation Generation
The project uses MkDocs to generate and serve documentation. All documentation files are stored in the docs/ directory, and MkDocs automatically builds them into a static website. Contributors can preview the documentation locally by running uv run mkdocs serve, which starts a live server on http://localhost:8000. To build the documentation for deployment, use uv run mkdocs build. MkDocs helps keep documentation organized, easy to update, and consistent with the project’s structure.

### 4. Continuous Integration (CI)
​​The project uses GitHub Actions for continuous integration to automatically check code quality and stability. The CI pipeline runs whenever a contributor opens a pull request or pushes new commits. It includes several jobs: linting and formatting (using Ruff and Black) to ensure code style, testing (with pytest and coverage) to verify functionality, and documentation build checks (with MkDocs) to confirm that documentation compiles correctly. These automated workflows help catch issues early, maintain consistent standards, and ensure that every change merged into the main branch keeps the project stable and reliable.

