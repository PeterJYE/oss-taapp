from slack_impl import SQLiteTokenStore, TokenBundle


def test_sqlite_token_store_crud_inmemory() -> None:
    store = SQLiteTokenStore()  # :memory:
    user = "U123"
    bundle = TokenBundle(access_token="xoxb-abc", scope="chat:write")

    assert store.has(user) is False
    assert store.load(user) is None

    store.save(user, bundle)
    assert store.has(user) is True
    got = store.load(user)
    assert got == bundle

    store.delete(user)
    assert store.has(user) is False
    assert store.load(user) is None

def test_sqlite_token_store_normalizes_loaded_row() -> None:
    """load() should normalize empty / None values and default token_type."""
    store = SQLiteTokenStore()
    user = "U999"

    # token_type intentionally set to empty string to exercise the fallback
    bundle = TokenBundle(
        access_token="tok-123",
        refresh_token=None,
        token_type="",
        scope=None,
        expires_at=None,
    )
    store.save(user, bundle)

    loaded = store.load(user)
    assert loaded is not None
    # access_token should round-trip
    assert loaded.access_token == "tok-123"
    # empty token_type -> default "Bearer"
    assert loaded.token_type == "Bearer"
    # None fields should stay None
    assert loaded.refresh_token is None
    assert loaded.scope is None
    assert loaded.expires_at is None


def test_sqlite_token_store_on_conflict_update_overwrites_row() -> None:
    """Saving the same user_id twice should update all fields."""
    store = SQLiteTokenStore()
    user = "U777"

    first = TokenBundle(
        access_token="old-token",
        refresh_token="r1",
        token_type="Bearer",
        scope="chat:write",
        expires_at=1111.0,
    )
    store.save(user, first)

    # Overwrite with a completely different bundle
    second = TokenBundle(
        access_token="new-token",
        refresh_token=None,
        token_type="Custom",
        scope="channels:read",
        expires_at=2222.5,
    )
    store.save(user, second)

    loaded = store.load(user)
    assert loaded is not None
    assert loaded.access_token == "new-token"
    assert loaded.refresh_token is None
    assert loaded.token_type == "Custom"
    assert loaded.scope == "channels:read"
    assert loaded.expires_at == 2222.5


def test_sqlite_token_store_clear_and_close_are_safe() -> None:
    """clear() removes all rows and close() can be called safely."""
    store = SQLiteTokenStore()
    store.save("U1", TokenBundle(access_token="t1"))
    store.save("U2", TokenBundle(access_token="t2"))

    assert store.has("U1")
    assert store.has("U2")

    # clear() should wipe all rows
    store.clear()
    assert not store.has("U1")
    assert not store.has("U2")
    assert store.load("U1") is None
    assert store.load("U2") is None

    # close() should not raise, even if called more than once
    store.close()
    store.close()
