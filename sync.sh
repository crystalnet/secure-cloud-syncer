#!/bin/bash

# Exit on error
set -e

# Configuration
LOCAL_DIR="$1"
REMOTE_DIR="gdrive_encrypted:"
LOG_FILE="$HOME/.rclone/sync.log"

# Check if local directory is provided
if [ -z "$LOCAL_DIR" ]; then
    echo "Usage: $0 <local_directory>"
    echo "Example: $0 ~/Documents"
    exit 1
fi

# Check if local directory exists
if [ ! -d "$LOCAL_DIR" ]; then
    echo "Error: Local directory $LOCAL_DIR does not exist"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Start sync
log_message "Starting sync from $LOCAL_DIR to $REMOTE_DIR"

# Perform the sync with encryption
rclone sync "$LOCAL_DIR" "$REMOTE_DIR" \
    --verbose \
    --log-file "$LOG_FILE" \
    --log-level INFO \
    --transfers 4 \
    --checkers 8 \
    --contimeout 60s \
    --timeout 300s \
    --retries 3 \
    --low-level-retries 10 \
    --vfs-cache-mode writes

# Check sync status
if [ $? -eq 0 ]; then
    log_message "Sync completed successfully"
else
    log_message "Sync failed with error code $?"
    exit 1
fi 