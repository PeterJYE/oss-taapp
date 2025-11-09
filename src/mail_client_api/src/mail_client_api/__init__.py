"""Mail Client API package.

This package provides the abstract interface for mail client implementations.
"""

from .client import Client as Client
from .client import get_client as get_client
from .message import Message as Message
from .message import get_message as get_message
