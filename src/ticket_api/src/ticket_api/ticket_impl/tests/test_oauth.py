"""Unit tests for OAuth helper functions."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response
from ticket_impl.oauth import (
    build_authorize_url,
    extract_cloud_id_from_token,
    fetch_cloud_id_from_api,
    fetch_project_key_from_api,
    get_valid_access_token,
)
from ticket_impl.storage import Token

# Test constants
DEFAULT_EXPIRY_SECONDS = 3600


def create_mock_jwt(claims: dict[str, str]) -> str:
    """Create a mock JWT token with the given claims."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    signature = "fake-signature"
    return f"{header}.{payload}.{signature}"


class TestExtractCloudIdFromToken:
    """Tests for extract_cloud_id_from_token function."""

    def test_extract_cloud_id_from_standard_field(self) -> None:
        """Test extracting cloud ID from standard cloud_id field."""
        claims = {"cloud_id": "test-cloud-123"}
        token = create_mock_jwt(claims)

        result = extract_cloud_id_from_token(token)

        assert result == "test-cloud-123"

    def test_extract_cloud_id_from_atlassian_url_field(self) -> None:
        """Test extracting cloud ID from Atlassian URL field."""
        claims = {"https://api.atlassian.com/site/cloud_id": "url-cloud-456"}
        token = create_mock_jwt(claims)

        result = extract_cloud_id_from_token(token)

        assert result == "url-cloud-456"

    def test_extract_cloud_id_from_camel_case_field(self) -> None:
        """Test extracting cloud ID from camelCase cloudId field."""
        claims = {"cloudId": "camel-cloud-789"}
        token = create_mock_jwt(claims)

        result = extract_cloud_id_from_token(token)

        assert result == "camel-cloud-789"

    def test_extract_cloud_id_from_sid_field(self) -> None:
        """Test extracting cloud ID from sid field."""
        claims = {"sid": "sid-cloud-000"}
        token = create_mock_jwt(claims)

        result = extract_cloud_id_from_token(token)

        assert result == "sid-cloud-000"

    def test_extract_cloud_id_from_scope(self) -> None:
        """Test extracting cloud ID from scope string."""
        claims = {"scope": "read:jira-user site:a1b2c3d4-e5f6-7890-1234"}
        token = create_mock_jwt(claims)

        result = extract_cloud_id_from_token(token)

        assert result == "a1b2c3d4-e5f6-7890-1234"

    def test_extract_cloud_id_invalid_jwt_format(self) -> None:
        """Test extracting cloud ID from invalid JWT format."""
        invalid_token = "not.a.valid.token.with.extra.parts"

        result = extract_cloud_id_from_token(invalid_token)

        assert result is None

    def test_extract_cloud_id_invalid_base64(self) -> None:
        """Test extracting cloud ID with invalid base64 encoding."""
        invalid_token = "header.!!!invalid-base64!!!.signature"

        result = extract_cloud_id_from_token(invalid_token)

        assert result is None

    def test_extract_cloud_id_invalid_json(self) -> None:
        """Test extracting cloud ID with invalid JSON payload."""
        header = base64.urlsafe_b64encode(b"{}").decode().rstrip("=")
        payload = base64.urlsafe_b64encode(b"{invalid json").decode().rstrip("=")

        invalid_token = f"{header}.{payload}.sig"

        result = extract_cloud_id_from_token(invalid_token)

        assert result is None

    def test_extract_cloud_id_no_fields_found(self) -> None:
        """Test extracting cloud ID when no cloud ID fields exist."""
        claims = {"some_other_field": "value"}
        token = create_mock_jwt(claims)

        result = extract_cloud_id_from_token(token)

        assert result is None

    def test_extract_cloud_id_priority_order(self) -> None:
        """Test that cloud ID fields are checked in priority order."""
        claims = {
            "https://api.atlassian.com/site/cloud_id": "priority1",
            "cloud_id": "priority2",
            "cloudId": "priority3",
        }
        token = create_mock_jwt(claims)

        result = extract_cloud_id_from_token(token)

        assert result == "priority1"


class TestBuildAuthorizeUrl:
    """Tests for build_authorize_url function."""

    @patch("ticket_impl.oauth.settings")
    def test_build_authorize_url_contains_required_params(self, mock_settings: MagicMock) -> None:
        """Test that authorize URL contains all required parameters."""
        mock_settings.oauth_client_id = "test-client-id"
        mock_settings.oauth_redirect_uri = "http://localhost:8000/callback"

        url = build_authorize_url(state="test-state-123")

        assert "auth.atlassian.com/authorize" in url
        assert "client_id=test-client-id" in url
        assert "redirect_uri=" in url
        assert "state=test-state-123" in url
        assert "scope=" in url
        assert "response_type=code" in url

    @patch("ticket_impl.oauth.settings")
    def test_build_authorize_url_state_parameter(self, mock_settings: MagicMock) -> None:
        """Test that state parameter is correctly included."""
        mock_settings.oauth_client_id = "client"
        mock_settings.oauth_redirect_uri = "http://localhost/callback"

        url = build_authorize_url(state="unique-state-xyz")

        assert "state=unique-state-xyz" in url


class TestGetValidAccessToken:
    """Tests for get_valid_access_token function."""

    @pytest.mark.asyncio
    async def test_test_user_bypass(self) -> None:
        """Test that test users bypass OAuth and get test token."""
        result = await get_valid_access_token(user_id="test-user-123")

        assert result == "test-access-token"

    @pytest.mark.asyncio
    @patch("ticket_impl.oauth.get_tokens")
    async def test_no_tokens_error(self, mock_get_tokens: MagicMock) -> None:
        """Test error when user has no tokens."""
        mock_get_tokens.return_value = None

        with pytest.raises(RuntimeError, match="User has no token"):
            await get_valid_access_token(user_id="user-no-tokens")

    @pytest.mark.asyncio
    @patch("ticket_impl.oauth.is_expired")
    @patch("ticket_impl.oauth.get_tokens")
    async def test_valid_token_returned(
        self,
        mock_get_tokens: MagicMock,
        mock_is_expired: MagicMock,
    ) -> None:
        """Test returning valid non-expired token."""
        mock_token = Token(
            user_id="user-123",
            access_token="valid-access-token",
            refresh_token="refresh",
            expires_at=9999999999,
        )
        mock_get_tokens.return_value = mock_token
        mock_is_expired.return_value = False

        result = await get_valid_access_token(user_id="user-123")

        assert result == "valid-access-token"

    @pytest.mark.asyncio
    @patch("ticket_impl.oauth.refresh_access_token")
    @patch("ticket_impl.oauth.is_expired")
    @patch("ticket_impl.oauth.get_tokens")
    async def test_expired_token_refreshed(
        self,
        mock_get_tokens: MagicMock,
        mock_is_expired: MagicMock,
        mock_refresh: MagicMock,
    ) -> None:
        """Test that expired token is refreshed."""
        mock_token = Token(
            user_id="user-456",
            access_token="expired-token",
            refresh_token="refresh",
            expires_at=0,
        )
        mock_get_tokens.return_value = mock_token
        mock_is_expired.return_value = True
        mock_refresh.return_value = "new-refreshed-token"

        result = await get_valid_access_token(user_id="user-456")

        assert result == "new-refreshed-token"
        mock_refresh.assert_called_once()


class TestFetchProjectKeyFromApi:
    """Tests for fetch_project_key_from_api function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_project_key_from_list_response(self) -> None:
        """Test fetching project key from list API response."""
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-456/rest/api/3/projects",
        ).mock(
            return_value=Response(
                200,
                json=[
                    {"key": "PROJ1", "name": "Project 1"},
                    {"key": "PROJ2", "name": "Project 2"},
                ],
            ),
        )

        result = await fetch_project_key_from_api(
            access_token="token-123",
            cloud_id="cloud-456",
        )

        assert result == "PROJ1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_project_key_from_dict_with_values(self) -> None:
        """Test fetching project key from dict API response with values field."""
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-000/rest/api/3/projects",
        ).mock(
            side_effect=[
                Response(404),  # First endpoint fails
            ],
        )
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-000/rest/api/3/projects/search",
        ).mock(
            return_value=Response(
                200,
                json={"values": [{"key": "TEST", "name": "Test Project"}]},
            ),
        )

        result = await fetch_project_key_from_api(
            access_token="token-789",
            cloud_id="cloud-000",
        )

        assert result == "TEST"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_project_key_no_projects(self) -> None:
        """Test fetching project key when no projects exist."""
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-444/rest/api/3/projects",
        ).mock(return_value=Response(200, json=[]))
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-444/rest/api/3/projects/search",
        ).mock(return_value=Response(200, json={}))
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-444/rest/api/2/projects",
        ).mock(return_value=Response(200, json=[]))

        result = await fetch_project_key_from_api(
            access_token="token-333",
            cloud_id="cloud-444",
        )

        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_project_key_non_200_status(self) -> None:
        """Test fetching project key with non-200 status code."""
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-888/rest/api/3/projects",
        ).mock(return_value=Response(401))
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-888/rest/api/3/projects/search",
        ).mock(return_value=Response(401))
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-888/rest/api/2/projects",
        ).mock(return_value=Response(401))

        result = await fetch_project_key_from_api(
            access_token="token-777",
            cloud_id="cloud-888",
        )

        assert result is None


class TestFetchCloudIdFromApi:
    """Tests for fetch_cloud_id_from_api function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_cloud_id_from_list_response(self) -> None:
        """Test fetching cloud ID from list API response."""
        respx.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
        ).mock(
            return_value=Response(
                200,
                json=[
                    {"id": "cloud-id-123", "name": "Jira Site 1"},
                    {"id": "cloud-id-456", "name": "Jira Site 2"},
                ],
            ),
        )

        result = await fetch_cloud_id_from_api(access_token="token-abc")

        assert result == "cloud-id-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_cloud_id_from_dict_response(self) -> None:
        """Test fetching cloud ID from dict API response."""
        respx.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
        ).mock(return_value=Response(200, json={"id": "cloud-id-dict"}))

        result = await fetch_cloud_id_from_api(access_token="token-def")

        assert result == "cloud-id-dict"

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_cloud_id_empty_list(self) -> None:
        """Test fetching cloud ID when list is empty."""
        respx.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
        ).mock(return_value=Response(200, json=[]))

        result = await fetch_cloud_id_from_api(access_token="token-empty")

        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_cloud_id_list_no_id_field(self) -> None:
        """Test fetching cloud ID when list items have no id field."""
        respx.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
        ).mock(
            return_value=Response(
                200,
                json=[{"name": "Jira Site", "other_field": "value"}],
            ),
        )

        result = await fetch_cloud_id_from_api(access_token="token-no-id")

        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_cloud_id_non_200_status(self) -> None:
        """Test fetching cloud ID with non-200 status code."""
        respx.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
        ).mock(return_value=Response(401))

        result = await fetch_cloud_id_from_api(access_token="token-invalid")

        assert result is None


class TestExchangeCodeForTokens:
    """Tests for exchange_code_for_tokens function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_for_tokens_success(self) -> None:
        """Test successfully exchanging auth code for tokens."""
        respx.post(
            "https://auth.atlassian.com/oauth/token",
        ).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            ),
        )

        from ticket_impl.oauth import exchange_code_for_tokens

        access, refresh, expires_in = await exchange_code_for_tokens(
            user_id="user-exchange",
            code="auth-code-123",
        )

        assert access == "new-access"
        assert refresh == "new-refresh"
        assert expires_in == DEFAULT_EXPIRY_SECONDS

    @pytest.mark.asyncio
    @respx.mock
    async def test_exchange_code_default_expiry(self) -> None:
        """Test exchange with default expiry time."""
        respx.post(
            "https://auth.atlassian.com/oauth/token",
        ).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "token-a",
                    "refresh_token": "token-r",
                },
            ),
        )

        from ticket_impl.oauth import exchange_code_for_tokens

        _, _, expires_in = await exchange_code_for_tokens(
            user_id="user-default",
            code="code",
        )

        assert expires_in == DEFAULT_EXPIRY_SECONDS


class TestRefreshAccessToken:
    """Tests for refresh_access_token function."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_refresh_access_token_success(self) -> None:
        """Test successfully refreshing access token."""
        from ticket_impl.oauth import refresh_access_token
        from ticket_impl.storage import upsert_tokens

        # Setup initial token
        upsert_tokens(
            user_id="user-refresh",
            access="old-access",
            refresh="refresh-token-123",
            expires_in_sec=3600,
        )

        respx.post(
            "https://auth.atlassian.com/oauth/token",
        ).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "new-access-token",
                    "expires_in": 7200,
                },
            ),
        )

        result = await refresh_access_token(user_id="user-refresh")

        assert result == "new-access-token"

    @pytest.mark.asyncio
    async def test_refresh_access_token_no_tokens_error(self) -> None:
        """Test refreshing when user has no stored tokens."""
        from ticket_impl.oauth import refresh_access_token

        with pytest.raises(RuntimeError, match="No tokens for user"):
            await refresh_access_token(user_id="no-such-user")


class TestFetchProjectKeyApiErrors:
    """Tests for error handling in fetch_project_key_from_api."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_project_key_request_error(self) -> None:
        """Test handling request error when fetching projects."""
        import httpx

        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-err/rest/api/3/projects",
        ).mock(side_effect=httpx.RequestError("Connection error"))
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-err/rest/api/3/projects/search",
        ).mock(side_effect=httpx.RequestError("Connection error"))
        respx.get(
            "https://api.atlassian.com/ex/jira/cloud-err/rest/api/2/projects",
        ).mock(side_effect=httpx.RequestError("Connection error"))

        from ticket_impl.oauth import fetch_project_key_from_api

        result = await fetch_project_key_from_api(
            access_token="token-err",
            cloud_id="cloud-err",
        )

        assert result is None


class TestFetchCloudIdApiErrors:
    """Tests for error handling in fetch_cloud_id_from_api."""

    @pytest.mark.asyncio
    async def test_fetch_cloud_id_request_error(self) -> None:
        """Test handling request error when fetching cloud ID."""
        from ticket_impl.oauth import fetch_cloud_id_from_api

        # Mock will fail naturally when no mock is set up
        result = await fetch_cloud_id_from_api(access_token="token-will-fail")

        # Should return None instead of raising
        assert result is None
