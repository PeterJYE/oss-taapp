"""Convenience module exposing the FastAPI app for tests and scripts."""

from mail_client_service.src import main as _main

app = _main.app
get_client_dep = _main.get_client_dep

__all__ = ["app", "get_client_dep"]
