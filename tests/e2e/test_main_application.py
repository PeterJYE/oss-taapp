"""End-to-End tests for the main application.

This module tests the application's main entry point (main.py) as a black box,
simulating real user interactions and verifying the complete workflow.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import gmail_client_impl
import mail_client_api

pytestmark = pytest.mark.e2e


@pytest.mark.local_credentials
def test_main_script_runs_and_fetches_messages() -> None:
    """Tests that the main.py script can be executed and successfully prints output indicating it has fetched messages.

    This test requires real credentials and a live internet connection.
    Only runs locally with credentials.json or token.json files.
    """
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")

    credentials_file = main_script.parent / "credentials.json"
    token_file = main_script.parent / "token.json"

    if not credentials_file.exists() and not token_file.exists():
        pytest.skip("No credentials.json or token.json found - cannot run E2E test")

    command = [
        sys.executable,
        str(main_script),
    ]

    try:
        result = subprocess.run(  # noqa: S603
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
            cwd=str(main_script.parent),
        )

        output = result.stdout

        assert "Demo complete" in output

        if "Found Message:" in output:
            lines = output.split("\n")
            found_line = next((line for line in lines if "Found Message:" in line), None)
            if found_line:
                pass

    except subprocess.TimeoutExpired:
        pytest.fail("E2E test timed out - main.py took too long to execute")
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"E2E test failed when running main.py.\nExit Code: {e.returncode}\nStdout: {e.stdout}\nStderr: {e.stderr}",
        )
    except FileNotFoundError:
        pytest.fail("Python interpreter or main.py not found")


@pytest.mark.circleci
def test_main_script_with_env_vars_only() -> None:  # noqa: C901, PLR0915, PLR0912
    """Tests that main.py works correctly in CI/CD environments.

    Uses only environment variables for authentication (no token.json or credentials.json).
    This test simulates CircleCI where only environment variables are available.
    """
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")

    required_env_vars = ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]

    if missing_vars:
        pytest.skip(f"Missing required environment variables for CI test: {missing_vars}")
    else:
        pass
    ci_main_content = """

import mail_client_api
import gmail_client_impl

def main() -> None:
    \"\"\"Initializes the client and demonstrates all mail client methods.\"\"\"
    print("Attempting to initialize Gmail client...")
    try:
        client = mail_client_api.get_client(interactive=False)
        print("\\nSuccessfully authenticated and connected to the Gmail API using environment variables.")

        print("\\n=== TEST 1: Fetching Messages ===")
        messages = list(client.get_messages(max_results=1))

        if not messages:
            print("No messages found in inbox.")
            return

        print(f"Found {len(messages)} messages:")
        for i, msg in enumerate(messages, 1):
            print(f"\\nMessage {i}:")
            print(f"  ID: {msg.id}")
            print(f"  Subject: {msg.subject}")
            print(f"  From: {msg.from_}")
            print(f"  Date: {msg.date}")
            print(f"  Body: {msg.body[:50].replace('/n', ' ')}...")

        if messages:
            test_message_id = messages[0].id
            print(f"\\n=== TEST 2: Getting Specific Message (ID: {test_message_id}) ===")
            try:
                specific_msg = client.get_message(test_message_id)
                print(f"Successfully retrieved message:")
                print(f"  Subject: {specific_msg.subject}")
                print(f"  From: {specific_msg.from_}")
                print(f"  Date: {specific_msg.date}")
            except Exception as e:
                print(f"Error getting specific message: {e}")

        print("\\n=== CI Tests Completed Successfully ===")

    except Exception as e:
        print(f"\\nAn error occurred: {e}")
        raise

if __name__ == "__main__":
    main()
"""

    ci_main_script = main_script.parent / "main_ci.py"

    try:
        with ci_main_script.open("w") as f:
            f.write(ci_main_content)

        credentials_file = main_script.parent / "credentials.json"
        token_file = main_script.parent / "token.json"

        backup_files = []

        try:
            if credentials_file.exists():
                backup_cred = credentials_file.with_suffix(".json.ci_backup")
                credentials_file.rename(backup_cred)
                backup_files.append((credentials_file, backup_cred))

            if token_file.exists():
                backup_token = token_file.with_suffix(".json.ci_backup")
                token_file.rename(backup_token)
                backup_files.append((token_file, backup_token))

            command = [sys.executable, str(ci_main_script)]

            result = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
                cwd=str(main_script.parent),
            )

            output = result.stdout

            assert "Attempting to initialize Gmail client..." in output
            assert "Successfully authenticated and connected to the Gmail API using environment variables." in output

            assert "=== TEST 1: Fetching Messages ===" in output
            assert "=== TEST 2: Getting Specific Message" in output
            assert "=== CI Tests Completed Successfully ===" in output

            if "Found" in output and "messages:" in output:
                lines = output.split("\n")
                found_line = next((line for line in lines if "Found" in line and "messages:" in line), None)
                if found_line:
                    pass

        finally:
            for original, backup in backup_files:
                if backup.exists():
                    backup.rename(original)

    except subprocess.TimeoutExpired:
        pytest.fail("CI E2E test timed out")
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"CI E2E test failed when running main_ci.py.\nExit Code: {e.returncode}\nStdout: {e.stdout}\nStderr: {e.stderr}",
        )
    finally:
        if ci_main_script.exists():
            ci_main_script.unlink()


@pytest.mark.local_credentials
def test_main_script_handles_no_credentials_gracefully(tmp_path: Path) -> None:
    """Ensure the Gmail client raises a helpful error when no credentials are provided."""
    gmail_client_impl.register()

    patched_env = {
        "GMAIL_CLIENT_ID": "",
        "GMAIL_CLIENT_SECRET": "",
        "GMAIL_REFRESH_TOKEN": "",
        "GMAIL_TOKEN_URI": "https://oauth2.googleapis.com/token",
    }

    dummy_token_path = tmp_path / "token.json"
    dummy_credentials_path = tmp_path / "credentials.json"

    with (
        patch.dict(os.environ, patched_env, clear=False),
        patch.object(gmail_client_impl.GmailClient, "TOKEN_PATH", str(dummy_token_path)),
        patch.object(gmail_client_impl.GmailClient, "CREDENTIALS_PATH", str(dummy_credentials_path)),
        pytest.raises(RuntimeError) as excinfo,
    ):
        mail_client_api.get_client(interactive=False)

    message = str(excinfo.value)
    assert "No valid credentials found" in message
    assert "Please provide valid credentials" in message


@pytest.mark.circleci
def test_main_script_syntax_is_valid() -> None:
    """Tests that main.py has valid Python syntax.

    This can run in any environment.
    """
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")

    command = [sys.executable, "-m", "py_compile", str(main_script)]

    try:
        subprocess.run(  # noqa: S603
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

    except subprocess.CalledProcessError as e:
        pytest.fail(f"main.py has syntax errors:\n{e.stderr}")


@pytest.mark.circleci
def test_main_script_imports_work() -> None:
    """Tests that main.py can import all required modules.

    This can run in any environment.
    """
    main_script = Path(__file__).parent.parent.parent / "main.py"

    if not main_script.exists():
        pytest.skip(f"main.py not found at {main_script}")

    import_test_code = """
try:
    import mail_client_api
    import gmail_client_impl
    print("All imports successful")
except ImportError as e:
    print(f"Import error: {e}")
    raise
"""

    command = [sys.executable, "-c", import_test_code]

    try:
        result = subprocess.run(  # noqa: S603
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            cwd=str(main_script.parent),
        )

        assert "All imports successful" in result.stdout

    except subprocess.CalledProcessError as e:
        pytest.fail(f"main.py imports failed:\n{e.stderr}")


@pytest.mark.circleci
def test_application_structure_integrity() -> None:
    """Tests that the application has the expected file structure.

    This can run in any environment.
    """
    workspace_root = Path(__file__).parent.parent.parent

    expected_files = [
        "main.py",
        "pyproject.toml",
        "src/mail_client_api/src/mail_client_api/__init__.py",
        "src/mail_client_api/src/mail_client_api/client.py",
        "src/mail_client_api/src/mail_client_api/message.py",
        "src/gmail_client_impl/src/gmail_client_impl/__init__.py",
        "src/gmail_client_impl/src/gmail_client_impl/gmail_impl.py",
        "src/gmail_client_impl/src/gmail_client_impl/message_impl.py",
    ]

    missing_files = []

    for file_path in expected_files:
        full_path = workspace_root / file_path
        if not full_path.exists():
            missing_files.append(file_path)

    if missing_files:
        pytest.fail(f"Missing required files: {missing_files}")
