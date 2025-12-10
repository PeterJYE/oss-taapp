"""Tests for the `openai_client_impl.storage` module."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from openai_client_impl.storage import (
    ConversationStore,
    UserCred,
    delete_conversation,
    get_conversation_data,
    get_openai_key,
    init_db,
    save_conversation,
    set_openai_key,
)


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    # Reimport to get the new database URL
    import importlib
    import openai_client_impl.storage

    importlib.reload(openai_client_impl.storage)
    init_db()
    return db_path


@pytest.fixture
def temp_fernet_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up a temporary Fernet key for testing."""
    key_file = tmp_path / ".fernet_key"
    from cryptography.fernet import Fernet

    test_key = Fernet.generate_key()
    key_file.write_bytes(test_key)
    monkeypatch.setenv("FERNET_KEY", test_key.decode())
    # Reimport to get the new key
    import importlib
    import openai_client_impl.storage

    importlib.reload(openai_client_impl.storage)


def test_init_db_creates_directory(temp_db: Path) -> None:
    """Test that init_db creates the .data directory if it doesn't exist."""
    # The fixture already calls init_db, so we just verify the database exists
    assert temp_db.exists()


def test_set_and_get_openai_key(temp_db: Path, temp_fernet_key: None) -> None:
    """Test setting and getting an OpenAI API key."""
    subject = "test_user"
    api_key = "sk-test123456789"

    # Set the key
    set_openai_key(subject, api_key)

    # Get the key back
    retrieved_key = get_openai_key(subject)
    assert retrieved_key == api_key


def test_get_openai_key_nonexistent_user(temp_db: Path, temp_fernet_key: None) -> None:
    """Test getting a key for a user that doesn't exist."""
    retrieved_key = get_openai_key("nonexistent_user")
    assert retrieved_key is None


def test_get_openai_key_no_key_set(temp_db: Path, temp_fernet_key: None) -> None:
    """Test getting a key for a user with no key set."""
    subject = "user_no_key"
    # Create user without setting key
    from openai_client_impl.storage import SessionLocal, UserCred

    with SessionLocal() as db:
        user = UserCred(subject=subject)
        db.add(user)
        db.commit()

    retrieved_key = get_openai_key(subject)
    assert retrieved_key is None


def test_set_openai_key_updates_existing(temp_db: Path, temp_fernet_key: None) -> None:
    """Test that setting a key for an existing user updates it."""
    subject = "existing_user"
    first_key = "sk-first"
    second_key = "sk-second"

    set_openai_key(subject, first_key)
    assert get_openai_key(subject) == first_key

    set_openai_key(subject, second_key)
    assert get_openai_key(subject) == second_key


def test_save_conversation_new(temp_db: Path) -> None:
    """Test saving a new conversation."""
    conv_id = "conv-123"
    subject = "test_user"
    created_at = "2025-01-01T00:00:00Z"
    messages_json = '[{"role": "user", "content": "hello"}]'

    save_conversation(conv_id, subject, created_at, messages_json)

    # Verify it was saved
    data = get_conversation_data(conv_id)
    assert data is not None
    assert data[0] == subject
    assert data[1] == created_at
    assert data[2] == messages_json


def test_save_conversation_updates_existing(temp_db: Path) -> None:
    """Test that saving a conversation with existing ID updates it."""
    conv_id = "conv-456"
    subject = "test_user"
    created_at = "2025-01-01T00:00:00Z"
    first_messages = '[{"role": "user", "content": "first"}]'
    second_messages = '[{"role": "user", "content": "second"}]'

    save_conversation(conv_id, subject, created_at, first_messages)
    save_conversation(conv_id, subject, created_at, second_messages)

    # Verify it was updated
    data = get_conversation_data(conv_id)
    assert data is not None
    assert data[2] == second_messages


def test_get_conversation_data_existing(temp_db: Path) -> None:
    """Test getting conversation data for an existing conversation."""
    conv_id = "conv-789"
    subject = "test_user"
    created_at = "2025-01-01T00:00:00Z"
    messages_json = '[{"role": "user", "content": "test"}]'

    save_conversation(conv_id, subject, created_at, messages_json)
    data = get_conversation_data(conv_id)

    assert data is not None
    assert data == (subject, created_at, messages_json)


def test_get_conversation_data_nonexistent(temp_db: Path) -> None:
    """Test getting conversation data for a nonexistent conversation."""
    data = get_conversation_data("nonexistent_conv")
    assert data is None


def test_delete_conversation_existing(temp_db: Path) -> None:
    """Test deleting an existing conversation."""
    conv_id = "conv-delete"
    subject = "test_user"
    created_at = "2025-01-01T00:00:00Z"
    messages_json = '[{"role": "user", "content": "delete me"}]'

    save_conversation(conv_id, subject, created_at, messages_json)
    assert get_conversation_data(conv_id) is not None

    result = delete_conversation(conv_id)
    assert result is True
    assert get_conversation_data(conv_id) is None


def test_delete_conversation_nonexistent(temp_db: Path) -> None:
    """Test deleting a nonexistent conversation."""
    result = delete_conversation("nonexistent_conv")
    assert result is False


def test_fernet_key_generation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Fernet key is generated when not set and saved to file."""
    from cryptography.fernet import Fernet
    
    # Set up temp directory and change to it
    key_file = tmp_path / ".fernet_key"
    data_dir = tmp_path / ".data"
    data_dir.mkdir()
    
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        
        # Remove FERNET_KEY from environment to trigger key generation
        monkeypatch.delenv("FERNET_KEY", raising=False)
        
        # Patch the module-level FERNET_KEY
        import openai_client_impl.storage
        original_fernet_key = openai_client_impl.storage.FERNET_KEY
        openai_client_impl.storage.FERNET_KEY = None
        
        # Use the _fernet function indirectly by setting/getting a key
        subject = "test_fernet_user"
        api_key = "sk-fernet-test"
        
        set_openai_key(subject, api_key)
        retrieved_key = get_openai_key(subject)
        
        assert retrieved_key == api_key
        assert key_file.exists(), "Fernet key file should be created"
        
        # Restore
        openai_client_impl.storage.FERNET_KEY = original_fernet_key
        
    finally:
        os.chdir(original_cwd)


def test_fernet_key_from_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that existing Fernet key file is used when FERNET_KEY env var is not set."""
    from cryptography.fernet import Fernet
    
    # Set up temp directory
    key_file = tmp_path / ".fernet_key"
    existing_key = Fernet.generate_key()
    key_file.write_bytes(existing_key)
    
    data_dir = tmp_path / ".data"
    data_dir.mkdir()
    
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        
        # Remove FERNET_KEY from environment
        monkeypatch.delenv("FERNET_KEY", raising=False)
        
        # Patch the module-level FERNET_KEY
        import openai_client_impl.storage
        original_fernet_key = openai_client_impl.storage.FERNET_KEY
        openai_client_impl.storage.FERNET_KEY = None
        
        # Use the _fernet function indirectly
        subject = "test_existing_key_user"
        api_key = "sk-existing-key-test"
        
        set_openai_key(subject, api_key)
        retrieved_key = get_openai_key(subject)
        
        assert retrieved_key == api_key
        
        # Restore
        openai_client_impl.storage.FERNET_KEY = original_fernet_key
        
    finally:
        os.chdir(original_cwd)

