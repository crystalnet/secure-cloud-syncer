#!/bin/bash

# Exit on error
set -e

# Configuration
RCLONE_VERSION="1.66.0"
RCLONE_CONFIG_DIR="$HOME/.rclone"
RCLONE_CONFIG_FILE="$RCLONE_CONFIG_DIR/rclone.conf"
TEMPLATE_FILE=".rclone.conf.template"

# Function to print messages
print_message() {
    echo "=== $1 ==="
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check rclone version
check_rclone_version() {
    if ! command_exists rclone; then
        print_message "Installing rclone v$RCLONE_VERSION"
        case "$(uname -s)" in
            Darwin)
                # macOS
                brew install rclone
                ;;
            Linux)
                # Linux
                curl -O https://downloads.rclone.org/v$RCLONE_VERSION/rclone-v$RCLONE_VERSION-linux-amd64.zip
                unzip rclone-v$RCLONE_VERSION-linux-amd64.zip
                sudo mv rclone-v$RCLONE_VERSION-linux-amd64/rclone /usr/local/bin/
                rm -rf rclone-v$RCLONE_VERSION-linux-amd64*
                ;;
            MINGW*|CYGWIN*|MSYS*)
                # Windows
                curl -O https://downloads.rclone.org/v$RCLONE_VERSION/rclone-v$RCLONE_VERSION-windows-amd64.zip
                unzip rclone-v$RCLONE_VERSION-windows-amd64.zip
                mv rclone-v$RCLONE_VERSION-windows-amd64/rclone.exe /usr/local/bin/
                rm -rf rclone-v$RCLONE_VERSION-windows-amd64*
                ;;
            *)
                echo "Unsupported operating system"
                exit 1
                ;;
        esac
    fi

    # Verify rclone version
    if ! rclone version | grep -q "v$RCLONE_VERSION"; then
        print_message "Warning: Installed rclone version does not match required version $RCLONE_VERSION"
        print_message "Please update rclone manually"
    fi
}

# Function to setup rclone
setup_rclone() {
    print_message "Setting up rclone configuration"

    # Create rclone config directory if it doesn't exist
    mkdir -p "$RCLONE_CONFIG_DIR"

    # Check if rclone.conf already exists
    if [ -f "$RCLONE_CONFIG_FILE" ]; then
        print_message "rclone.conf already exists"
        return
    fi

    # Copy template if it exists
    if [ -f "$TEMPLATE_FILE" ]; then
        cp "$TEMPLATE_FILE" "$RCLONE_CONFIG_FILE"
        print_message "Copied template configuration"
    else
        print_message "No template configuration found"
    fi

    # Configure Google Drive
    print_message "Configuring Google Drive"
    rclone config

    # Configure encryption
    print_message "Configuring encryption"
    rclone config
}

# Main script
print_message "Starting rclone setup"

# Check and install rclone
check_rclone_version

# Setup rclone configuration
setup_rclone

print_message "Rclone setup completed successfully" 