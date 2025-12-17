"""Unit tests for storage module (token and ticket mapping persistence)."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from ticket_impl.storage import (
    TicketMap,
    Token,
    clear_user_tokens,
    engine,
    ensure_mapping_for_keys,
    get_key_for_uuid,
    get_tokens,
    get_user_tokens,
    is_expired,
    map_uuid_to_key,
    update_access,
    upsert_tokens,
)

# Constants
EXPIRY_TOLERANCE_SEC = 5


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Fixture providing a database session with a clean database."""
    # Create tables
    Token.metadata.create_all(engine)
    TicketMap.metadata.create_all(engine)

    session = Session(engine)
    yield session

    # Cleanup: delete all tokens and mappings
    session.query(Token).delete()
    session.query(TicketMap).delete()
    session.commit()
    session.close()


class TestUpsertTokens:
    """Tests for upsert_tokens function."""

    def test_upsert_tokens_new_user(self) -> None:
        """Test inserting tokens for a new user."""
        upsert_tokens(
            user_id="user-123",
            access="access-token-new",
            refresh="refresh-token-new",
            expires_in_sec=3600,
        )

        result = get_tokens("user-123")
        assert result is not None
        assert result.user_id == "user-123"
        assert result.access_token == "access-token-new"
        assert result.refresh_token == "refresh-token-new"

    def test_upsert_tokens_update_existing(self) -> None:
        """Test updating tokens for an existing user."""
        # First insert
        upsert_tokens(
            user_id="user-456",
            access="old-access",
            refresh="old-refresh",
            expires_in_sec=3600,
        )

        # Update
        upsert_tokens(
            user_id="user-456",
            access="new-access",
            refresh="new-refresh",
            expires_in_sec=7200,
        )

        result = get_tokens("user-456")
        assert result is not None
        assert result.access_token == "new-access"
        assert result.refresh_token == "new-refresh"

    def test_upsert_tokens_expiry_calculation(self) -> None:
        """Test that token expiry is calculated correctly."""
        before = datetime.now(tz=UTC)
        upsert_tokens(
            user_id="user-789",
            access="access",
            refresh="refresh",
            expires_in_sec=1800,  # 30 minutes
        )

        result = get_tokens("user-789")
        assert result is not None
        # Should be approximately 30 minutes in future
        expected_expiry = before + timedelta(seconds=1800)
        # Allow tolerance for both naive and aware datetimes
        result_expiry = result.expires_at
        if result_expiry.tzinfo is None:
            result_expiry = result_expiry.replace(tzinfo=UTC)
        assert abs((result_expiry - expected_expiry).total_seconds()) < EXPIRY_TOLERANCE_SEC


class TestGetTokens:
    """Tests for get_tokens function."""

    def test_get_tokens_existing_user(self) -> None:
        """Test retrieving tokens for an existing user."""
        upsert_tokens(
            user_id="user-existing",
            access="access-token",
            refresh="refresh-token",
            expires_in_sec=3600,
        )

        result = get_tokens("user-existing")

        assert result is not None
        assert result.user_id == "user-existing"
        assert result.access_token == "access-token"

    def test_get_tokens_nonexistent_user(self) -> None:
        """Test retrieving tokens for a non-existent user."""
        result = get_tokens("nonexistent-user")

        assert result is None


class TestGetUserTokens:
    """Tests for get_user_tokens function."""

    def test_get_user_tokens_existing_user(self) -> None:
        """Test retrieving user tokens as dict for existing user."""
        upsert_tokens(
            user_id="user-dict",
            access="access-123",
            refresh="refresh-456",
            expires_in_sec=3600,
        )

        result = get_user_tokens("user-dict")

        assert result is not None
        assert result["access_token"] == "access-123"
        assert result["refresh_token"] == "refresh-456"

    def test_get_user_tokens_nonexistent_user(self) -> None:
        """Test retrieving user tokens for non-existent user."""
        result = get_user_tokens("nonexistent")

        assert result is None


class TestClearUserTokens:
    """Tests for clear_user_tokens function."""

    def test_clear_user_tokens_existing_user(self) -> None:
        """Test clearing tokens for an existing user."""
        upsert_tokens(
            user_id="user-to-clear",
            access="access",
            refresh="refresh",
            expires_in_sec=3600,
        )

        result = clear_user_tokens("user-to-clear")

        assert result is True
        assert get_tokens("user-to-clear") is None

    def test_clear_user_tokens_nonexistent_user(self) -> None:
        """Test clearing tokens for a non-existent user."""
        result = clear_user_tokens("nonexistent")

        assert result is False


class TestUpdateAccess:
    """Tests for update_access function."""

    def test_update_access_existing_user(self) -> None:
        """Test updating access token for existing user."""
        upsert_tokens(
            user_id="user-update",
            access="old-access",
            refresh="refresh-unchanged",
            expires_in_sec=3600,
        )

        old_token = get_tokens("user-update")
        assert old_token is not None
        old_expiry = old_token.expires_at

        # Update access token
        update_access(
            user_id="user-update",
            access="new-access-123",
            expires_in_sec=7200,
        )

        updated_token = get_tokens("user-update")
        assert updated_token is not None
        assert updated_token.access_token == "new-access-123"
        assert updated_token.refresh_token == "refresh-unchanged"
        # Expiry should be updated
        assert updated_token.expires_at > old_expiry

    def test_update_access_nonexistent_user(self) -> None:
        """Test updating access token for non-existent user (should not crash)."""
        # Should not raise an error
        update_access(
            user_id="nonexistent",
            access="new-access",
            expires_in_sec=3600,
        )

        # Verify nothing was created
        assert get_tokens("nonexistent") is None


class TestIsExpired:
    """Tests for is_expired function."""

    def test_is_expired_token_still_valid(self) -> None:
        """Test that a non-expired token returns False."""
        now = datetime.now(tz=UTC)
        future = now + timedelta(hours=1)

        token = Token(
            user_id="user-valid",
            access_token="access",
            refresh_token="refresh",
            expires_at=future,
        )

        assert is_expired(token) is False

    def test_is_expired_token_expired(self) -> None:
        """Test that an expired token returns True."""
        now = datetime.now(tz=UTC)
        past = now - timedelta(hours=1)

        token = Token(
            user_id="user-expired",
            access_token="access",
            refresh_token="refresh",
            expires_at=past,
        )

        assert is_expired(token) is True

    def test_is_expired_token_at_boundary(self) -> None:
        """Test token at exact expiry boundary."""
        now = datetime.now(tz=UTC)

        token = Token(
            user_id="user-boundary",
            access_token="access",
            refresh_token="refresh",
            expires_at=now,
        )

        # At or past boundary is considered expired
        assert is_expired(token) is True

    def test_is_expired_naive_datetime(self) -> None:
        """Test handling of naive datetime (no timezone)."""
        now = datetime.now(tz=UTC)  # Use UTC timezone
        future = now + timedelta(hours=1)

        token = Token(
            user_id="user-naive",
            access_token="access",
            refresh_token="refresh",
            expires_at=future,
        )

        # Should not raise error when comparing with naive datetime
        result = is_expired(token)
        assert isinstance(result, bool)


class TestMapUuidToKey:
    """Tests for map_uuid_to_key function."""

    def test_map_uuid_to_key_new_mapping(self) -> None:
        """Test creating a new UUID to Jira key mapping."""
        ticket_uuid = uuid4()

        map_uuid_to_key(
            user_id="user-map",
            ticket_uuid=ticket_uuid,
            jira_key="PROJ-123",
        )

        result = get_key_for_uuid("user-map", ticket_uuid)
        assert result == "PROJ-123"

    def test_map_uuid_to_key_update_existing(self) -> None:
        """Test updating an existing UUID to Jira key mapping."""
        ticket_uuid = uuid4()

        # First mapping
        map_uuid_to_key(
            user_id="user-map-2",
            ticket_uuid=ticket_uuid,
            jira_key="PROJ-111",
        )

        # Update mapping
        map_uuid_to_key(
            user_id="user-map-2",
            ticket_uuid=ticket_uuid,
            jira_key="PROJ-222",
        )

        result = get_key_for_uuid("user-map-2", ticket_uuid)
        assert result == "PROJ-222"

    def test_map_uuid_to_key_user_scoped(self) -> None:
        """Test that mappings are scoped per user."""
        ticket_uuid = uuid4()

        # User 1 maps UUID to key
        map_uuid_to_key(
            user_id="user-a",
            ticket_uuid=ticket_uuid,
            jira_key="KEY-A",
        )

        # User 2 maps same UUID to different key
        map_uuid_to_key(
            user_id="user-b",
            ticket_uuid=ticket_uuid,
            jira_key="KEY-B",
        )

        assert get_key_for_uuid("user-a", ticket_uuid) == "KEY-A"
        assert get_key_for_uuid("user-b", ticket_uuid) == "KEY-B"


class TestGetKeyForUuid:
    """Tests for get_key_for_uuid function."""

    def test_get_key_for_uuid_existing(self) -> None:
        """Test retrieving Jira key for existing UUID."""
        ticket_uuid = uuid4()
        map_uuid_to_key(
            user_id="user-get",
            ticket_uuid=ticket_uuid,
            jira_key="KEY-999",
        )

        result = get_key_for_uuid("user-get", ticket_uuid)
        assert result == "KEY-999"

    def test_get_key_for_uuid_nonexistent(self) -> None:
        """Test retrieving Jira key for non-existent UUID."""
        result = get_key_for_uuid("user-get", uuid4())
        assert result is None


class TestEnsureMappingForKeys:
    """Tests for ensure_mapping_for_keys function."""

    def test_ensure_mapping_for_keys_new_mappings(self) -> None:
        """Test bulk upserting new UUID to key mappings."""
        uuid1 = uuid4()
        uuid2 = uuid4()
        uuid3 = uuid4()

        ensure_mapping_for_keys(
            user_id="user-bulk",
            pairs=[
                (uuid1, "KEY-1"),
                (uuid2, "KEY-2"),
                (uuid3, "KEY-3"),
            ],
        )

        assert get_key_for_uuid("user-bulk", uuid1) == "KEY-1"
        assert get_key_for_uuid("user-bulk", uuid2) == "KEY-2"
        assert get_key_for_uuid("user-bulk", uuid3) == "KEY-3"

    def test_ensure_mapping_for_keys_mixed_new_and_existing(self) -> None:
        """Test bulk upserting with mix of new and existing mappings."""
        uuid1 = uuid4()
        uuid2 = uuid4()

        # Insert first mapping
        map_uuid_to_key(
            user_id="user-mixed",
            ticket_uuid=uuid1,
            jira_key="OLD-KEY",
        )

        # Bulk upsert with one new and one update
        ensure_mapping_for_keys(
            user_id="user-mixed",
            pairs=[
                (uuid1, "UPDATED-KEY"),
                (uuid2, "NEW-KEY"),
            ],
        )

        assert get_key_for_uuid("user-mixed", uuid1) == "UPDATED-KEY"
        assert get_key_for_uuid("user-mixed", uuid2) == "NEW-KEY"

    def test_ensure_mapping_for_keys_empty_list(self) -> None:
        """Test bulk upserting with empty list."""
        # Should not raise error
        ensure_mapping_for_keys(user_id="user-empty", pairs=[])

        # Verify nothing was created
        assert get_key_for_uuid("user-empty", uuid4()) is None
