#!/bin/bash

# Exit on error
set -e

# Configuration
LAUNCH_AGENT_NAME="com.secure_cloud_syncer.monitor"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="com.secure_cloud_syncer.monitor.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to check if the service is running
check_service() {
    launchctl list | grep -q "$LAUNCH_AGENT_NAME"
    return $?
}

# Function to start the service
start_service() {
    echo "Starting Secure Cloud Syncer monitoring service..."
    launchctl load "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    if check_service; then
        echo "Service started successfully"
    else
        echo "Failed to start service"
        exit 1
    fi
}

# Function to stop the service
stop_service() {
    echo "Stopping Secure Cloud Syncer monitoring service..."
    launchctl unload "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    if ! check_service; then
        echo "Service stopped successfully"
    else
        echo "Failed to stop service"
        exit 1
    fi
}

# Function to install the service
install_service() {
    echo "Installing Secure Cloud Syncer monitoring service..."
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$LAUNCH_AGENT_DIR"
    
    # Copy the plist file
    cp "$SCRIPT_DIR/$PLIST_FILE" "$LAUNCH_AGENT_DIR/"
    
    # Set correct permissions
    chmod 644 "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    
    echo "Service installed successfully"
}

# Function to uninstall the service
uninstall_service() {
    echo "Uninstalling Secure Cloud Syncer monitoring service..."
    
    # Stop the service if it's running
    if check_service; then
        stop_service
    fi
    
    # Remove the plist file
    rm -f "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    
    echo "Service uninstalled successfully"
}

# Function to show service status
show_status() {
    if check_service; then
        echo "Secure Cloud Syncer monitoring service is running"
    else
        echo "Secure Cloud Syncer monitoring service is not running"
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install    Install the monitoring service"
    echo "  uninstall  Uninstall the monitoring service"
    echo "  start      Start the monitoring service"
    echo "  stop       Stop the monitoring service"
    echo "  status     Show the service status"
    echo "  help       Show this help message"
}

# Main script
case "$1" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    status)
        show_status
        ;;
    help|*)
        show_usage
        ;;
esac 