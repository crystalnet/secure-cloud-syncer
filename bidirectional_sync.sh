#!/bin/bash

# Exit on error
set -e

# Configuration
LOCAL_DIR="$1"
REMOTE_DIR="gdrive_encrypted:"
LOG_FILE="$HOME/.rclone/bidirectional_sync.log"
EXCLUDE_RESOURCE_FORKS=false
SYNC_INTERVAL=300  # 5 minutes in seconds

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --exclude-resource-forks)
            EXCLUDE_RESOURCE_FORKS=true
            shift
            ;;
        --interval)
            SYNC_INTERVAL="$2"
            shift 2
            ;;
        *)
            LOCAL_DIR="$1"
            shift
            ;;
    esac
done

# Check if local directory is provided
if [ -z "$LOCAL_DIR" ]; then
    echo "Error: No local directory specified"
    echo "Usage: $0 [--exclude-resource-forks] [--interval SECONDS] <local_directory>"
    echo "Example: $0 ~/Documents"
    echo "Example: $0 --exclude-resource-forks ~/Documents"
    echo "Example: $0 --interval 600 ~/Documents"
    echo ""
    echo "This will set up bidirectional sync between your local directory and Google Drive"
    echo "while preserving the file structure and names. Files will be encrypted in the cloud."
    echo ""
    echo "Options:"
    echo "  --exclude-resource-forks  Exclude macOS resource fork files (._*)"
    echo "  --interval SECONDS        Set the sync interval in seconds (default: 300)"
    exit 1
fi

# Check if rclonesync is installed
if ! command -v rclonesync &> /dev/null; then
    echo "rclonesync is not installed. Please install it first."
    echo "Visit https://github.com/twooster/rclonesync for installation instructions."
    echo ""
    echo "You can install it with:"
    echo "  pip install rclonesync"
    exit 1
fi

# Expand the path if it contains ~
LOCAL_DIR="${LOCAL_DIR/#\~/$HOME}"

# Check if local directory exists
if [ ! -d "$LOCAL_DIR" ]; then
    echo "Error: Local directory '$LOCAL_DIR' does not exist"
    exit 1
fi

# Check if local directory is readable
if [ ! -r "$LOCAL_DIR" ]; then
    echo "Error: Local directory '$LOCAL_DIR' is not readable"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Build the exclude patterns
EXCLUDE_PATTERNS="--exclude \".DS_Store\" --exclude \".DS_Store/**\" --exclude \"**/.DS_Store\" \
    --exclude \".Trash/**\" --exclude \"**/.Trash/**\" \
    --exclude \".localized\" --exclude \"**/.localized\" \
    --exclude \".Spotlight-V100\" --exclude \"**/.Spotlight-V100/**\" \
    --exclude \".fseventsd\" --exclude \"**/.fseventsd/**\" \
    --exclude \".TemporaryItems\" --exclude \"**/.TemporaryItems/**\" \
    --exclude \".VolumeIcon.icns\" --exclude \"**/.VolumeIcon.icns\" \
    --exclude \".DocumentRevisions-V100\" --exclude \"**/.DocumentRevisions-V100/**\" \
    --exclude \".com.apple.timemachine.donotpresent\" --exclude \"**/.com.apple.timemachine.donotpresent\" \
    --exclude \".AppleDouble\" --exclude \"**/.AppleDouble/**\" \
    --exclude \".LSOverride\" --exclude \"**/.LSOverride/**\" \
    --exclude \"Icon?\" --exclude \"**/Icon?\""

# Add resource fork exclusions if requested
if [ "$EXCLUDE_RESOURCE_FORKS" = true ]; then
    echo "Excluding macOS resource fork files (._*)"
    EXCLUDE_PATTERNS="$EXCLUDE_PATTERNS --exclude \"._*\" --exclude \"**/._*\""
fi

# Start bidirectional sync
log_message "Starting bidirectional sync between $LOCAL_DIR and $REMOTE_DIR"
log_message "Files will be encrypted in the cloud but file names and structure will be preserved"
log_message "Sync interval: $SYNC_INTERVAL seconds"

echo ""
echo "Starting bidirectional sync process..."
echo "This will keep your local directory and Google Drive in sync in both directions."
echo "Files will be encrypted in the cloud but file names and structure will be preserved."
echo "Press Ctrl+C to stop the sync process."
echo "----------------------------------------"

# Run rclonesync with the specified options
eval "rclonesync \"$LOCAL_DIR\" \"$REMOTE_DIR\" \
    --rclone-args \"$EXCLUDE_PATTERNS --verbose --log-file $LOG_FILE\" \
    --rclone-timeout 300 \
    --rclone-retries 3 \
    --rclone-low-level-retries 10 \
    --rclone-transfers 4 \
    --rclone-checkers 8 \
    --rclone-contimeout 60s \
    --rclone-timeout 300s \
    --rclone-retries 3 \
    --rclone-low-level-retries 10 \
    --rclone-progress \
    --rclone-stats-one-line \
    --rclone-stats 5s \
    --sync-interval $SYNC_INTERVAL \
    --log-level INFO \
    --log-file $LOG_FILE" 