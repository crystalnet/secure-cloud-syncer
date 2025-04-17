#!/bin/bash

# Exit on error
set -e

echo "Setting up rclone with Google Drive and encryption..."

# Check if rclone is installed
if ! command -v rclone &> /dev/null; then
    echo "rclone is not installed. Please install it first."
    echo "Visit https://rclone.org/downloads/ for installation instructions."
    exit 1
fi

# Create necessary directories
mkdir -p ~/.config/rclone
mkdir -p ~/.rclone

# Create Google Drive remote
echo "Setting up Google Drive remote..."
rclone config create gdrive drive

# Get encrypted folder name
read -p "Enter name for encrypted folder in Google Drive [secure_vault]: " ENCRYPTED_FOLDER
ENCRYPTED_FOLDER=${ENCRYPTED_FOLDER:-secure_vault}
echo "Using folder name: $ENCRYPTED_FOLDER"
read -p "Is this correct? [Y/n]: " CONFIRM
if [[ $CONFIRM =~ ^[Nn]$ ]]; then
    echo "Setup cancelled. Please run the script again."
    exit 1
fi

# Create encrypted remote
echo "Setting up encrypted remote..."
rclone config create gdrive_encrypted crypt

# Get encryption passwords
read -s -p "Enter your encryption password: " ENCRYPTION_PASSWORD
echo
read -s -p "Enter your salt password: " SALT_PASSWORD
echo

# Update the encrypted remote configuration with passwords and encryption settings
echo "Updating encryption settings..."
rclone config update gdrive_encrypted \
    remote "gdrive:$ENCRYPTED_FOLDER" \
    password "$ENCRYPTION_PASSWORD" \
    password2 "$SALT_PASSWORD" \
    filename_encryption off \
    directory_name_encryption false

# Create the encrypted directory in Google Drive
echo "Creating encrypted directory in Google Drive..."
if ! rclone mkdir "gdrive:$ENCRYPTED_FOLDER"; then
    echo "Error: Failed to create encrypted directory in Google Drive"
    exit 1
fi

# Verify the configuration
echo "Verifying encryption settings..."
if ! grep -q "filename_encryption = off" ~/.config/rclone/rclone.conf; then
    echo "Warning: Failed to set filename encryption to 'off'"
    echo "Please manually edit ~/.config/rclone/rclone.conf and add under [gdrive_encrypted]:"
    echo "filename_encryption = off"
    echo "directory_name_encryption = false"
fi

# Set proper permissions
chmod 600 ~/.config/rclone/rclone.conf

echo "Setup complete! Please:"
echo "1. Verify these settings are present under [gdrive_encrypted] in ~/.config/rclone/rclone.conf:"
echo "   filename_encryption = off"
echo "   directory_name_encryption = false"
echo "2. Run 'rclone lsd gdrive:' to test the connection"
echo "3. Run 'rclone lsd gdrive_encrypted:' to test the encrypted remote"
echo ""
echo "For security, make sure to:"
echo "- Keep your encryption passwords safe"
echo "- Never commit rclone.conf to version control"
echo "- Regularly backup your rclone.conf file" 