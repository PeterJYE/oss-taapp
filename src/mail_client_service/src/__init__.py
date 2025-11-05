"""Mail Client Service package."""

try:
    from .main import app as app
    from .main import get_client_dep as get_client_dep
except ImportError:
    app = None  # type: ignore[assignment]
    get_client_dep = None  # type: ignore[assignment]
