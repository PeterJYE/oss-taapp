"""OAuth helper functions for Jira Cloud (Auth0) flows."""

from __future__ import annotations

import base64
import json
import logging
import re
from http import HTTPStatus
from typing import cast
from urllib.parse import urlencode

import httpx

from .config import settings
from .storage import Token, get_tokens, is_expired, update_access, upsert_tokens

logger = logging.getLogger(__name__)

AUTH_BASE = "https://auth.atlassian.com"
TOKEN_URL = f"{AUTH_BASE}/oauth/token"
SCOPE = "read:jira-user read:jira-work write:jira-work offline_access"
AUDIENCE = "api.atlassian.com"

# JWT parts count
JWT_PARTS = 3
# Base64 padding value
BASE64_PADDING = 4


def extract_cloud_id_from_token(access_token: str) -> str | None:
    """Extract Jira Cloud ID from JWT access token.

    The JWT payload may contain cloud_id in various formats depending on OAuth scope.
    """
    try:
        # JWT format: header.payload.signature
        parts = access_token.split(".")
        if len(parts) != JWT_PARTS:
            return None

        # Decode the payload (add padding if needed)
        payload = parts[1]
        padding = BASE64_PADDING - len(payload) % BASE64_PADDING
        if padding != BASE64_PADDING:
            payload += "=" * padding

        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)

        # Try multiple possible cloud_id field names
        cloud_id: str | None = (
            claims.get("https://api.atlassian.com/site/cloud_id")
            or claims.get("cloud_id")
            or claims.get("cloudId")
            or claims.get("sid")  # Sometimes it's stored as 'sid'
        )

        if cloud_id:
            return cloud_id

        # If still not found, check the 'scope' field which may contain site references
        if "scope" not in claims:
            return None

        scope = claims["scope"]
        # Extract cloud ID from scope string like "site:xxx cloud:xxx"
        match = re.search(r"site:([a-f0-9\-]+)", scope)
        return match.group(1) if match else None
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        logger.debug("Failed to extract cloud ID from token: %s", e)
        return None


def build_authorize_url(state: str) -> str:
    """Build the browser URL to start OAuth authorization."""
    params = {
        "audience": AUDIENCE,
        "client_id": settings.oauth_client_id,
        "scope": SCOPE,
        "redirect_uri": settings.oauth_redirect_uri,
        "response_type": "code",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_BASE}/authorize?{urlencode(params)}"


async def exchange_code_for_tokens(user_id: str, code: str) -> tuple[str, str, int]:
    """Exchange authorization code for access/refresh tokens."""
    data = {
        "grant_type": "authorization_code",
        "client_id": settings.oauth_client_id,
        "client_secret": settings.oauth_client_secret,
        "code": code,
        "redirect_uri": settings.oauth_redirect_uri,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(TOKEN_URL, json=data)
        r.raise_for_status()
        payload = r.json()
    access = payload["access_token"]
    refresh = payload["refresh_token"]
    expires_in = int(payload.get("expires_in", 3600))
    upsert_tokens(user_id, access, refresh, expires_in)
    return access, refresh, expires_in


async def refresh_access_token(user_id: str) -> str:
    """Use refresh token to obtain a new access token."""
    tok: Token | None = get_tokens(user_id)
    if not tok:
        msg = "No tokens for user; authenticate first (/auth/login)."
        raise RuntimeError(msg)
    data = {
        "grant_type": "refresh_token",
        "client_id": settings.oauth_client_id,
        "client_secret": settings.oauth_client_secret,
        "refresh_token": tok.refresh_token,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(TOKEN_URL, json=data)
        r.raise_for_status()
        payload = r.json()
    access = cast("str", payload["access_token"])
    expires_in = int(payload.get("expires_in", 3600))
    update_access(user_id, access, expires_in)
    return access


async def get_valid_access_token(user_id: str) -> str:
    """Return a non-expired access token, refreshing if needed."""
    # Allow test users to bypass OAuth
    if user_id.startswith("test-"):
        return "test-access-token"

    tok = get_tokens(user_id)
    if not tok:
        msg = "User has no token; complete OAuth."
        raise RuntimeError(msg)
    if is_expired(tok):
        return await refresh_access_token(user_id)
    return tok.access_token


async def fetch_project_key_from_api(access_token: str, cloud_id: str) -> str | None:
    """Fetch the first available project key from the Jira instance.

    Returns the project key of the first accessible project, or None if no projects found.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Try multiple endpoints to find projects
            endpoints = [
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/projects",
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/projects/search",
                f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/2/projects",
            ]

            for api_url in endpoints:
                try:
                    r = await client.get(
                        api_url,
                        headers=headers,
                        params={"maxResults": 1} if "search" in api_url else {},
                    )
                    if r.status_code == HTTPStatus.OK:
                        projects = r.json()
                        # Handle both array and dict responses
                        if isinstance(projects, list) and projects:
                            first_project = projects[0]
                            project_key = first_project.get("key")
                            if project_key:
                                return cast("str", project_key)
                        elif isinstance(projects, dict):
                            # If it's wrapped in a dict, check common field names
                            values = projects.get("values", projects.get("projects", []))
                            if values:
                                first_project = values[0]
                                project_key = first_project.get("key")
                                if project_key:
                                    return cast("str", project_key)
                except httpx.RequestError as e:
                    logger.debug("Failed to fetch projects from %s: %s", api_url, e)
                    continue

            return None
    except httpx.RequestError as e:
        logger.debug("Failed to fetch project key from API: %s", e)
        return None


async def fetch_cloud_id_from_api(access_token: str) -> str | None:
    """Fetch the Jira Cloud ID from the Atlassian API using the access token.

    Queries the /oauth/token/accessible-resources endpoint which returns an array of
    accessible Atlassian resources (sites/containers). Each resource has an 'id' field
    containing the cloud ID. We return the first Jira resource ID found.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {access_token}"}

            # Primary endpoint: /oauth/token/accessible-resources
            # Returns: [{"id": "cloud-id", "name": "Site name", "url": "...", ...}, ...]
            r = await client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers=headers,
            )
            if r.status_code == HTTPStatus.OK:
                resources = r.json()

                # Response should be a list of accessible resources
                if isinstance(resources, list) and resources:
                    # Return the first resource's ID (cloud ID)
                    # Usually there's only one, but Atlassian accounts can have multiple
                    for resource in resources:
                        cloud_id = resource.get("id")
                        if cloud_id:
                            return cast("str", cloud_id)
                # Fallback: if it's a dict (shouldn't happen but just in case)
                elif isinstance(resources, dict):
                    cloud_id = resources.get("id")
                    if cloud_id:
                        return cast("str", cloud_id)

            return None
    except httpx.RequestError as e:
        logger.debug("Failed to fetch cloud ID from API: %s", e)
        return None
