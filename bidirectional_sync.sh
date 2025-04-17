#!/bin/bash

# Exit on error
set -e

# Configuration
LOCAL_DIR="$1"
REMOTE_DIR="gdrive_encrypted:"
LOG_FILE="$HOME/.rclone/bidirectional_sync.log"
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
    echo "Example: $0 ~/secure_vault"
    echo "Example: $0 --exclude-resource-forks ~/secure_vault"
    echo ""
    echo "This will sync files between the specified local directory and Google Drive"
    echo "in both directions, ensuring that changes in either location are reflected in both."
    echo ""
    echo "Options:"
    echo "  --exclude-resource-forks  Exclude macOS resource fork files (._*)"
    exit 1
fi

# Check if required tools are installed
if ! command -v rclone &> /dev/null; then
    echo "rclone is not installed. Please run the setup script first: ./setup.sh"
    exit 1
fi

# Check rclone version for bisync support
RCLONE_VERSION=$(rclone version | grep -oP 'rclone v\K[0-9]+\.[0-9]+\.[0-9]+')
if [[ "$(echo "$RCLONE_VERSION 1.58.0" | awk '{print ($1 < $2)}')" -eq 1 ]]; then
    echo "Error: Your rclone version ($RCLONE_VERSION) is older than 1.58.0 which is required for bisync."
    echo "Please update rclone to version 1.58.0 or newer."
    echo "You can download it from: https://rclone.org/downloads/"
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

# Build the exclude patterns for rclone
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

# Start the sync process
log_message "Starting bidirectional sync between $LOCAL_DIR and $REMOTE_DIR"
log_message "Files will be encrypted in the cloud"

echo ""
echo "Starting bidirectional sync process..."
echo "This will sync files between your local directory and Google Drive in both directions."
echo "Files will be encrypted in the cloud."
echo "----------------------------------------"

# Run rclone bisync command
rclone bisync "$LOCAL_DIR" "$REMOTE_DIR" $EXCLUDE_PATTERNS --resync --verbose --log-file "$LOG_FILE"

log_message "Bidirectional sync completed successfully!" 