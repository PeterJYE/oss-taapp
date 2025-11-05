"""Top-level package shim for mail_client_api.

This repository places the real package under ``src/mail_client_api/src/mail_client_api``
for an editable ``src`` layout. Tests and other packages expect to import
``mail_client_api.client`` and ``mail_client_api.message`` (module objects) as
well as the top-level classes. Re-export both the symbols and the module
objects here to keep imports stable.
"""
from importlib import import_module

# Import the inner package (the real implementation under src/...)
_inner = import_module("mail_client_api.src.mail_client_api")

# Re-export commonly used symbols
Client = _inner.Client
get_client = _inner.get_client
Message = _inner.Message
get_message = _inner.get_message

# Also expose the actual submodules so callers can 'from mail_client_api import message'
client = import_module("mail_client_api.src.mail_client_api.client")
message = import_module("mail_client_api.src.mail_client_api.message")

