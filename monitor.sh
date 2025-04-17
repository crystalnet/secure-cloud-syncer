#!/bin/bash

# Exit on error
set -e

# Configuration
VAULT_DIR="$1"
REMOTE_DIR="gdrive_encrypted:"
LOG_FILE="$HOME/.rclone/monitor_sync.log"
EXCLUDE_RESOURCE_FORKS=false
DEBOUNCE_TIME=5  # seconds to wait after a change before triggering sync

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --exclude-resource-forks)
            EXCLUDE_RESOURCE_FORKS=true
            shift
            ;;
        --debounce)
            DEBOUNCE_TIME="$2"
            shift 2
            ;;
        *)
            VAULT_DIR="$1"
            shift
            ;;
    esac
done

# Check if vault directory is provided
if [ -z "$VAULT_DIR" ]; then
    echo "Error: No vault directory specified"
    echo "Usage: $0 [--exclude-resource-forks] [--debounce SECONDS] <vault_directory>"
    echo "Example: $0 ~/secure_vault"
    echo "Example: $0 --exclude-resource-forks ~/secure_vault"
    echo "Example: $0 --debounce 10 ~/secure_vault"
    echo ""
    echo "This will monitor your vault directory for changes and trigger a bidirectional sync"
    echo "when changes are detected. Files will be encrypted in the cloud."
    echo ""
    echo "Options:"
    echo "  --exclude-resource-forks  Exclude macOS resource fork files (._*)"
    echo "  --debounce SECONDS        Set the debounce time in seconds (default: 5)"
    exit 1
fi

# Check if required tools are installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Please run the setup script first: ./setup.sh"
    exit 1
fi

if ! command -v rclonesync &> /dev/null; then
    echo "rclonesync is not installed. Please run the setup script first: ./setup.sh"
    exit 1
fi

# Check if watchdog is installed
if ! python3 -c "import watchdog" &> /dev/null; then
    echo "watchdog is not installed. Please run the setup script first: ./setup.sh"
    exit 1
fi

# Expand the path if it contains ~
VAULT_DIR="${VAULT_DIR/#\~/$HOME}"

# Check if vault directory exists
if [ ! -d "$VAULT_DIR" ]; then
    echo "Error: Vault directory '$VAULT_DIR' does not exist"
    exit 1
fi

# Check if vault directory is readable
if [ ! -r "$VAULT_DIR" ]; then
    echo "Error: Vault directory '$VAULT_DIR' is not readable"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Build the exclude patterns for rclonesync
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

# Start the monitoring process
log_message "Starting monitoring of $VAULT_DIR"
log_message "Changes will trigger a bidirectional sync with $REMOTE_DIR"
log_message "Debounce time: $DEBOUNCE_TIME seconds"

echo ""
echo "Starting monitoring process..."
echo "This will watch your vault directory for changes and trigger a bidirectional sync"
echo "when changes are detected. Files will be encrypted in the cloud."
echo "Press Ctrl+C to stop the monitoring process."
echo "----------------------------------------"

# Run the Python module with the necessary arguments
python3 -m secure_cloud_syncer.sync.monitor "$VAULT_DIR" "$REMOTE_DIR" "$EXCLUDE_PATTERNS" "$DEBOUNCE_TIME" "$LOG_FILE" 