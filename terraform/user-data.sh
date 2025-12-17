#!/bin/bash
set -e

# Log everything with timestamps
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
echo "=========================================="
echo "Starting deployment at $(date)"
echo "=========================================="

# Update system (Ubuntu 22.04)
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies (including AWS CLI early)
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    unzip \
    gcc \
    python3.11-dev \
    awscli \
    wget

# Try to create CloudWatch log group early (so we can see logs if script fails)
LOG_GROUP="/aws/ec2/oss-taapp"
aws logs create-log-group --log-group-name "$LOG_GROUP" 2>/dev/null || true
aws logs put-retention-policy --log-group-name "$LOG_GROUP" --retention-in-days 7 2>/dev/null || true

# Install uv (install for ubuntu user, not root)
sudo -u ubuntu bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' || {
    echo "ERROR: Failed to install uv"
    exit 1
}
export PATH="/home/ubuntu/.local/bin:$PATH"

# Create app directory (owned by ubuntu user)
APP_DIR="/opt/oss-taapp"
TEMP_DIR="/tmp/repo-clone-$$"

# Clean up any existing temp directories
rm -rf $${TEMP_DIR} 2>/dev/null || true

# Validate repo_url is provided
if [ -z "${repo_url}" ] || [ "${repo_url}" = "" ]; then
    echo "ERROR: repo_url is required but not provided"
    exit 1
fi

# Validate URL format
if ! echo "${repo_url}" | grep -qE '^https?://'; then
    echo "ERROR: Invalid repo_url format: ${repo_url}"
    exit 1
fi

# Clone repository to temp directory first (as ubuntu user)
echo "Cloning repository: ${repo_url} (branch: ${repo_branch})"
mkdir -p $${TEMP_DIR}
chown ubuntu:ubuntu $${TEMP_DIR}

sudo -u ubuntu git clone -b ${repo_branch} --depth 1 ${repo_url} $${TEMP_DIR} || {
    echo "ERROR: Failed to clone repository from ${repo_url}"
    rm -rf $${TEMP_DIR}
    exit 1
}

# Verify pyproject.toml exists in cloned repo
if [ ! -f "$${TEMP_DIR}/pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in cloned repository"
    echo "Repository contents:"
    ls -la $${TEMP_DIR} || true
    rm -rf $${TEMP_DIR}
    exit 1
fi

# Move cloned content to app directory
rm -rf $${APP_DIR}/* $${APP_DIR}/.[!.]* $${APP_DIR}/..?* 2>/dev/null || true
mkdir -p $${APP_DIR}
chown ubuntu:ubuntu $${APP_DIR}
# Copy all files including hidden ones using cp with dot notation
sudo -u ubuntu bash -c "cp -r $${TEMP_DIR}/. $${APP_DIR}/" || {
    echo "ERROR: Failed to copy repository files"
    echo "Source directory contents:"
    ls -la $${TEMP_DIR} || true
    rm -rf $${TEMP_DIR}
    exit 1
}
chown -R ubuntu:ubuntu $${APP_DIR}

# Clean up temp directory
rm -rf $${TEMP_DIR}

# Verify pyproject.toml is in app directory
cd $${APP_DIR}
if [ ! -f "pyproject.toml" ]; then
    echo "ERROR: pyproject.toml not found in $${APP_DIR}"
    echo "Directory contents:"
    ls -la $${APP_DIR} || true
    exit 1
fi

echo "Repository cloned successfully to $${APP_DIR}"
echo "Found pyproject.toml at $${APP_DIR}/pyproject.toml"

# Install dependencies (as ubuntu user)
sudo -u ubuntu bash -c "cd $${APP_DIR} && /home/ubuntu/.local/bin/uv sync --all-packages" || {
    echo "ERROR: Failed to install dependencies"
    exit 1
}

# Clean up any unnecessary .md files that might have been created during terraform planning
# Remove any .md files in the app directory that are not part of the repository (e.g., plan output files)
find $${APP_DIR} -type f -name "*.md" ! -path "*/docs/*" ! -path "*/\.*" ! -name "README.md" -delete 2>/dev/null || true
# Clean up temporary .md files in /tmp from terraform operations
find /tmp -type f -name "*.md" -user ubuntu -mtime +0 -delete 2>/dev/null || true

# Set up environment variables
# Option 1: Read from Parameter Store (if configured)
# Option 2: Set directly here (less secure, but simpler)
# For now, we'll create a script that can be customized

cat > $${APP_DIR}/load-env.sh << 'ENVEOF'
#!/bin/bash
# Load environment variables
# You can either:
# 1. Read from AWS Parameter Store (recommended)
# 2. Set directly here (simpler, but less secure)

# Load from Parameter Store if available, otherwise use placeholders
# IMPORTANT: Set these in AWS Parameter Store for persistence:
#   aws ssm put-parameter --name "/oss-taapp/OPENAI_API_KEY" --value "your-key" --type "SecureString"
#   aws ssm put-parameter --name "/oss-taapp/OAUTH_CLIENT_ID" --value "your-client-id" --type "SecureString"
#   aws ssm put-parameter --name "/oss-taapp/OAUTH_CLIENT_SECRET" --value "your-secret" --type "SecureString"
#   aws ssm put-parameter --name "/oss-taapp/JIRA_CLOUD_ID" --value "your-cloud-id" --type "String"
#   aws ssm put-parameter --name "/oss-taapp/TICKET_SERVICE_USER_ID" --value "your-user-id" --type "String"
#   aws ssm put-parameter --name "/oss-taapp/JIRA_PROJECT_KEY" --value "your-project" --type "String"
#   aws ssm put-parameter --name "/oss-taapp/JIRA_REPORTER_EMAIL" --value "your-email" --type "String"
#   aws ssm put-parameter --name "/oss-taapp/CHAT_SERVICE_TOKEN" --value "your-token" --type "SecureString"
#   aws ssm put-parameter --name "/oss-taapp/CHAT_CHANNEL_ID" --value "your-channel-id" --type "String"

INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

# Try to read from Parameter Store, fallback to environment or placeholders
export OPENAI_API_KEY=$${OPENAI_API_KEY:-$(aws ssm get-parameter --name "/oss-taapp/OPENAI_API_KEY" --with-decryption --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-key-here")}
export OAUTH_CLIENT_ID=$${OAUTH_CLIENT_ID:-$(aws ssm get-parameter --name "/oss-taapp/OAUTH_CLIENT_ID" --with-decryption --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-client-id")}
export OAUTH_CLIENT_SECRET=$${OAUTH_CLIENT_SECRET:-$(aws ssm get-parameter --name "/oss-taapp/OAUTH_CLIENT_SECRET" --with-decryption --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-secret")}
export OAUTH_REDIRECT_URI="http://$INSTANCE_IP:8001/api/v1/auth/callback"
export JIRA_CLOUD_ID=$${JIRA_CLOUD_ID:-$(aws ssm get-parameter --name "/oss-taapp/JIRA_CLOUD_ID" --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-cloud-id")}
export DB_URL="sqlite:////opt/oss-taapp/jira_tokens.db"
export TICKET_SERVICE_USER_ID=$${TICKET_SERVICE_USER_ID:-$(aws ssm get-parameter --name "/oss-taapp/TICKET_SERVICE_USER_ID" --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-user-id")}
export JIRA_PROJECT_KEY=$${JIRA_PROJECT_KEY:-$(aws ssm get-parameter --name "/oss-taapp/JIRA_PROJECT_KEY" --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-project")}
export JIRA_REPORTER_EMAIL=$${JIRA_REPORTER_EMAIL:-$(aws ssm get-parameter --name "/oss-taapp/JIRA_REPORTER_EMAIL" --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-email")}
export CHAT_SERVICE_BASE_URL="$${CHAT_SERVICE_BASE_URL:-https://slack.com/api}"
export CHAT_SERVICE_TOKEN=$${CHAT_SERVICE_TOKEN:-$(aws ssm get-parameter --name "/oss-taapp/CHAT_SERVICE_TOKEN" --with-decryption --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-token")}
export CHAT_CHANNEL_ID=$${CHAT_CHANNEL_ID:-$(aws ssm get-parameter --name "/oss-taapp/CHAT_CHANNEL_ID" --query Parameter.Value --output text --region us-east-1 2>/dev/null || echo "your-channel-id")}
export AI_SERVICE_BASE_URL="http://localhost:8000"
ENVEOF

chmod +x $${APP_DIR}/load-env.sh
chown ubuntu:ubuntu $${APP_DIR}/load-env.sh

# Create systemd service for AI Service
cat > /etc/systemd/system/ai-service.service << 'SERVICEEOF'
[Unit]
Description=AI Service (OpenAI Client Service)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/oss-taapp
Environment="PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONPATH=/opt/oss-taapp/src"
ExecStart=/bin/bash -c 'source /opt/oss-taapp/load-env.sh && /home/ubuntu/.local/bin/uv run uvicorn openai_client_service.main:app --host 0.0.0.0 --port 8000'
Restart=always
RestartSec=10
StandardOutput=journal+file:/var/log/ai-service.log
StandardError=journal+file:/var/log/ai-service.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Create systemd service for Ticket Service
cat > /etc/systemd/system/ticket-service.service << 'SERVICEEOF'
[Unit]
Description=Ticket Service (JIRA)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/oss-taapp
Environment="PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONPATH=/opt/oss-taapp/src:/opt/oss-taapp/src/ticket_api/src/ticket_api"
ExecStart=/bin/bash -c 'source /opt/oss-taapp/load-env.sh && /home/ubuntu/.local/bin/uv run uvicorn ticket_service.main:app --host 0.0.0.0 --port 8001'
Restart=always
RestartSec=10
StandardOutput=journal+file:/var/log/ticket-service.log
StandardError=journal+file:/var/log/ticket-service.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Create systemd service for Integration Script
cat > /etc/systemd/system/integration.service << 'SERVICEEOF'
[Unit]
Description=Integration Script (Chat-AI-Ticket Integration)
After=network.target ai-service.service ticket-service.service
Requires=ai-service.service ticket-service.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/oss-taapp
Environment="PATH=/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONPATH=/opt/oss-taapp/src:/opt/oss-taapp/src/chat_api/src:/opt/oss-taapp/src/ticket_api/src/ticket_api:/opt/oss-taapp/src/ai_api/src/ai_api:/opt/oss-taapp/src/openai_adapter/src/openai_adapter"
ExecStart=/bin/bash -c 'source /opt/oss-taapp/load-env.sh && /home/ubuntu/.local/bin/uv run python integration_main.py'
Restart=always
RestartSec=10
StandardOutput=journal+file:/var/log/integration.log
StandardError=journal+file:/var/log/integration.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Enable and start services
systemctl daemon-reload
systemctl enable ai-service ticket-service integration

# Start services
systemctl start ai-service || true
systemctl start ticket-service || true
sleep 5
systemctl start integration || true

# Install CloudWatch agent
wget -q https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb -O /tmp/cw-agent.deb
dpkg -i /tmp/cw-agent.deb 2>/dev/null || apt-get install -f -y
rm -f /tmp/cw-agent.deb

# Final cleanup: remove any temporary .md files from terraform planning operations
find /tmp -type f -name "*.md" -user ubuntu -mtime +0 -delete 2>/dev/null || true
find $${APP_DIR} -type f -name "plan*.md" -o -name "terraform*.md" -delete 2>/dev/null || true

# CloudWatch config
mkdir -p /opt/aws/amazon-cloudwatch-agent/etc
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'CWEOF'
{"logs":{"logs_collected":{"files":{"collect_list":[{"file_path":"/var/log/user-data.log","log_group_name":"/aws/ec2/oss-taapp","log_stream_name":"user-data-{instance_id}"},{"file_path":"/var/log/ai-service.log","log_group_name":"/aws/ec2/oss-taapp","log_stream_name":"ai-service-{instance_id}"},{"file_path":"/var/log/ticket-service.log","log_group_name":"/aws/ec2/oss-taapp","log_stream_name":"ticket-service-{instance_id}"},{"file_path":"/var/log/integration.log","log_group_name":"/aws/ec2/oss-taapp","log_stream_name":"integration-{instance_id}"}]}}}}
CWEOF

systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

