"""
mail_client_api package
Defines the base Client class for all mail clients (e.g., GmailClient).
"""

__all__ = ["Client"]

class Client:
    """Base mail client interface that other mail clients inherit from."""

    def __init__(self, *args, **kwargs):
        """Initialize the client (optionally with credentials)."""
        self.connected = False

    def connect(self, *args, **kwargs):
        """Simulate connection setup."""
        self.connected = True
        print("Mail client connected")

    def send(self, *args, **kwargs):
        """Placeholder send method."""
        print("Mail client send() called")

