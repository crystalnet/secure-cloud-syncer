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

# Create encrypted remote
echo "Setting up Google Drive remote..."
rclone config create gdrive drive

# Create encrypted remote
echo "Setting up encrypted remote..."
rclone config create gdrive_encrypted crypt

# Create necessary directories
mkdir -p ~/.config/rclone
mkdir -p ~/.rclone

# Copy template to actual config if it doesn't exist
if [ ! -f ~/.config/rclone/rclone.conf ]; then
    if [ -f .rclone.conf.template ]; then
        cp .rclone.conf.template ~/.config/rclone/rclone.conf
        echo "Created rclone.conf from template. Please edit it with your actual credentials."
    else
        echo "Template file .rclone.conf.template not found!"
        exit 1
    fi
fi

# Set proper permissions
chmod 600 ~/.config/rclone/rclone.conf

echo "Setup complete! Please:"
echo "1. Edit ~/.config/rclone/rclone.conf with your actual credentials"
echo "2. Run 'rclone lsd gdrive:' to test the connection"
echo "3. Run 'rclone lsd gdrive_encrypted:' to test the encrypted remote"
echo ""
echo "For security, make sure to:"
echo "- Keep your encryption passwords safe"
echo "- Never commit rclone.conf to version control"
echo "- Regularly backup your rclone.conf file" 