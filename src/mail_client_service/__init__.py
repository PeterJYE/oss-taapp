"""Re-export FastAPI app and dependency helpers."""

from .src import main as _main

app = _main.app
get_client_dep = _main.get_client_dep
