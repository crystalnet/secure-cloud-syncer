#!/bin/bash

# Exit on error
set -e

# Configuration
LAUNCH_AGENT_NAME="com.secure_cloud_syncer.monitor"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="com.secure_cloud_syncer.monitor.plist"
LOG_DIR="$HOME/Library/Logs/secure_cloud_syncer"

# Function to print messages
print_message() {
    echo "=== $1 ==="
}

# Function to check if the service is running
check_service() {
    launchctl list | grep -q "$LAUNCH_AGENT_NAME"
    return $?
}

# Function to start the service
start_service() {
    print_message "Starting Secure Cloud Syncer monitoring service"
    launchctl load "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    if check_service; then
        print_message "Service started successfully"
    else
        print_message "Failed to start service"
        exit 1
    fi
}

# Function to stop the service
stop_service() {
    print_message "Stopping Secure Cloud Syncer monitoring service"
    launchctl unload "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    if ! check_service; then
        print_message "Service stopped successfully"
    else
        print_message "Failed to stop service"
        exit 1
    fi
}

# Function to install the service
install_service() {
    print_message "Installing Secure Cloud Syncer monitoring service"
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$LAUNCH_AGENT_DIR"
    
    # Create the plist file
    cat > "$LAUNCH_AGENT_DIR/$PLIST_FILE" << EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.secure_cloud_syncer.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>-m</string>
        <string>secure_cloud_syncer.manager</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/error.log</string>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/output.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOL
    
    # Set correct permissions
    chmod 644 "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    
    # Create the log directory
    mkdir -p "$LOG_DIR"
    
    print_message "Service installed successfully"
}

# Function to uninstall the service
uninstall_service() {
    print_message "Uninstalling Secure Cloud Syncer monitoring service"
    
    # Stop the service if it's running
    if check_service; then
        stop_service
    fi
    
    # Remove the plist file
    rm -f "$LAUNCH_AGENT_DIR/$PLIST_FILE"
    
    print_message "Service uninstalled successfully"
}

# Function to show service status
show_status() {
    if check_service; then
        print_message "Secure Cloud Syncer monitoring service is running"
    else
        print_message "Secure Cloud Syncer monitoring service is not running"
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