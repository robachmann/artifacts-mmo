#!/bin/bash
set -euo pipefail

# Load environment variables
source ./src/.env

# Check if SSO session is still valid; if not, login
if ! aws sts get-caller-identity --profile "$PROFILE_NAME" >/dev/null 2>&1; then
  echo "No valid AWS SSO session found. Logging in..."
  aws sso login --profile "$PROFILE_NAME"
else
  echo "Valid AWS SSO session found."
fi

# Download static resources
echo "Fetching static resources"
http "${BASE_URL}"/maps size==10000 \
  | jq --indent 2 . \
  > src/common_layer/artifactsmmo/static/all_maps.json

http "${BASE_URL}"/items size==10000 \
  | jq --indent 2 . \
  > src/common_layer/artifactsmmo/static/all_items.json

http "${BASE_URL}"/monsters size==10000 \
  | jq --indent 2 . \
  > src/common_layer/artifactsmmo/static/all_monsters.json

http "${BASE_URL}"/resources size==10000 \
  | jq --indent 2 . \
  > src/common_layer/artifactsmmo/static/all_resources.json

# Build SAM application
echo "Running sam build..."
if ! sam build; then
  echo "Error: 'sam build' failed. Exiting..."
  exit 1
fi

# Deploy SAM application
echo "Running sam deploy..."
if sam deploy --no-confirm-changeset --profile "$PROFILE_NAME"; then
  echo "Deployment successful. Sending Telegram notification..."
  http POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    chat_id="${TELEGRAM_CHAT_ID}" \
    text="🚀 New version deployed." \
    disable_notification=true --quiet
else
  echo "Error: 'sam deploy' failed. Exiting..."
  exit 1
fi

# Print timestamp
date
