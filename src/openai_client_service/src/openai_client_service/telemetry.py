"""Telemetry middleware for monitoring request latency, success, and failure rates."""

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# Metrics definitions
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Success and failure counters
REQUEST_SUCCESS = Counter(
    "http_requests_success_total",
    "Total number of successful HTTP requests (2xx, 3xx)",
    ["method", "endpoint"],
)

REQUEST_FAILURE = Counter(
    "http_requests_failure_total",
    "Total number of failed HTTP requests (4xx, 5xx)",
    ["method", "endpoint"],
)


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Middleware to collect telemetry data for all HTTP requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect telemetry metrics."""
        # Record start time
        start_time = time.time()

        # Get endpoint path (normalize for metrics)
        endpoint = request.url.path

        # Skip metrics endpoint to avoid infinite loops
        if endpoint == "/metrics":
            return await call_next(request)

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Count as 500 error if exception occurred
            status_code = 500
            raise
        finally:
            # Calculate latency
            latency = time.time() - start_time

            # Normalize endpoint for better aggregation (remove IDs, etc.)
            normalized_endpoint = self._normalize_endpoint(endpoint)

            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=normalized_endpoint,
                status_code=status_code,
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=normalized_endpoint,
                status_code=status_code,
            ).observe(latency)

            # Record success/failure
            if 200 <= status_code < 400:
                REQUEST_SUCCESS.labels(
                    method=request.method,
                    endpoint=normalized_endpoint,
                ).inc()
            else:
                REQUEST_FAILURE.labels(
                    method=request.method,
                    endpoint=normalized_endpoint,
                ).inc()

        return response

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        """Normalize endpoint by replacing IDs and UUIDs with placeholders."""
        import re

        # Replace UUIDs
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        endpoint = re.sub(uuid_pattern, "{id}", endpoint, flags=re.IGNORECASE)

        # Replace numeric IDs
        endpoint = re.sub(r"/\d+", "/{id}", endpoint)

        return endpoint


def metrics_endpoint(request: Request) -> StarletteResponse:
    """Endpoint to expose Prometheus metrics."""
    return StarletteResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
