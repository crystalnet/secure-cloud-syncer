#!/bin/bash

# Exit on error
set -e

# Configuration
LOCAL_DIR="$1"
REMOTE_DIR="gdrive_encrypted:"
LOG_FILE="$HOME/.rclone/sync.log"
EXCLUDE_RESOURCE_FORKS=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --exclude-resource-forks)
            EXCLUDE_RESOURCE_FORKS=true
            shift
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
    echo "Usage: $0 [--exclude-resource-forks] <local_directory>"
    echo "Example: $0 ~/Documents"
    echo "Example: $0 --exclude-resource-forks ~/Documents"
    echo ""
    echo "This will encrypt and sync the specified local directory to Google Drive"
    echo "while preserving the file structure and names."
    echo ""
    echo "Options:"
    echo "  --exclude-resource-forks  Exclude macOS resource fork files (._*)"
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

# Start sync
log_message "Starting sync from $LOCAL_DIR to $REMOTE_DIR"
log_message "Files will be encrypted but file names and structure will be preserved"

echo ""
echo "Starting sync process..."
echo "You will see progress information below:"
echo "----------------------------------------"

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

# Perform the sync with encryption
eval "rclone sync \"$LOCAL_DIR\" \"$REMOTE_DIR\" \
    --verbose \
    --progress \
    --stats-one-line \
    --stats 5s \
    --log-file \"$LOG_FILE\" \
    --transfers 4 \
    --checkers 8 \
    --contimeout 60s \
    --timeout 300s \
    --retries 3 \
    --low-level-retries 10 \
    $EXCLUDE_PATTERNS"

# Check sync status
if [ $? -eq 0 ]; then
    log_message "Sync completed successfully"
    echo ""
    echo "Your files have been encrypted and synced to Google Drive."
    echo "File names and directory structure have been preserved."
    echo "You can find your files in the encrypted folder in your Google Drive."
else
    log_message "Sync failed with error code $?"
    exit 1
fi 