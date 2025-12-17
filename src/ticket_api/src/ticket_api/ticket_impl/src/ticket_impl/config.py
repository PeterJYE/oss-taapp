"""Runtime settings for Jira Cloud + OAuth."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file from project root
# Use absolute path resolution to ensure we find .env regardless of working directory
env_path = None

# Strategy 1: Look up from config.py location (most reliable)
current = Path(__file__).resolve().parent
max_depth = 10  # Prevent infinite loops
depth = 0
while current != current.parent and depth < max_depth:
    env_file = current / ".env"
    if env_file.exists():
        env_path = env_file
        break
    current = current.parent
    depth += 1

# Strategy 2: Try current working directory
if not env_path:
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        env_path = cwd_env

# Strategy 3: Explicit fallback path (9 levels up from config.py)
if not env_path:
    fallback_path = Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent.parent.parent / ".env"
    if fallback_path.exists():
        env_path = fallback_path

# Load .env file with override to ensure latest values
if env_path and env_path.exists():
    # Use override=True to replace any existing env vars
    result = load_dotenv(env_path, override=True)
    # Also set explicitly in os.environ to be absolutely sure
    if result:
        import os
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
else:
    # Last resort: try current directory
    load_dotenv(override=False)


class Settings(BaseModel):
    """Container for environment-based configuration."""

    # Jira Cloud
    jira_cloud_id: str
    jira_api_base: str
    # Atlassian OAuth 2.0 (3LO)
    oauth_client_id: str
    oauth_client_secret: str
    oauth_redirect_uri: str
    # Token & mapping DB
    db_url: str = Field(default="sqlite:///./jira_tokens.db")


# Create settings instance - read directly from os.environ after .env is loaded
# These values MUST come from environment variables - no defaults
jira_cloud_id = os.environ.get("JIRA_CLOUD_ID")
if not jira_cloud_id:
    raise ValueError("JIRA_CLOUD_ID environment variable is required. Set it in your .env file.")

jira_api_base = os.environ.get(
    "JIRA_API_BASE",
    f"https://api.atlassian.com/ex/jira/{jira_cloud_id}",
)

oauth_client_id = os.environ.get("OAUTH_CLIENT_ID")
if not oauth_client_id:
    raise ValueError("OAUTH_CLIENT_ID environment variable is required. Set it in your .env file.")

oauth_client_secret = os.environ.get("OAUTH_CLIENT_SECRET")
if not oauth_client_secret:
    raise ValueError("OAUTH_CLIENT_SECRET environment variable is required. Set it in your .env file.")

oauth_redirect_uri = os.environ.get("OAUTH_REDIRECT_URI")
if not oauth_redirect_uri:
    raise ValueError("OAUTH_REDIRECT_URI environment variable is required. Set it in your .env file.")

settings = Settings(
    jira_cloud_id=jira_cloud_id,
    jira_api_base=jira_api_base,
    oauth_client_id=oauth_client_id,
    oauth_client_secret=oauth_client_secret,
    oauth_redirect_uri=oauth_redirect_uri,
    db_url=os.environ.get("DB_URL", "sqlite:///./jira_tokens.db"),
)
