#!/bin/bash

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos";;
        Linux*)     echo "linux";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

# Function to create and activate a virtual environment
setup_virtual_env() {
    print_message "Setting up Python virtual environment..."
    
    # Create virtual environment directory
    VENV_DIR="$HOME/.secure_cloud_syncer_venv"
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    print_message "Virtual environment activated at $VENV_DIR"
}

# Function to install dependencies on macOS
install_macos() {
    print_message "Installing dependencies for macOS..."
    
    # Check if Homebrew is installed
    if ! command_exists brew; then
        print_message "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install rclone
    if ! command_exists rclone; then
        print_message "Installing rclone..."
        brew install rclone
    else
        # Check rclone version for bisync support
        RCLONE_VERSION=$(rclone version | grep -oP 'rclone v\K[0-9]+\.[0-9]+\.[0-9]+')
        if [[ "$(echo "$RCLONE_VERSION 1.58.0" | awk '{print ($1 < $2)}')" -eq 1 ]]; then
            print_warning "Your rclone version ($RCLONE_VERSION) is older than 1.58.0 which is required for bisync."
            print_message "Updating rclone..."
            brew upgrade rclone
        fi
    fi
    
    # Install Python if not present (needed for monitoring)
    if ! command_exists python3; then
        print_message "Installing Python..."
        brew install python
    fi
    
    # Install pip if not present
    if ! command_exists pip3; then
        print_message "Installing pip..."
        python3 -m ensurepip --upgrade
    fi
    
    # Setup virtual environment
    setup_virtual_env
    
    # Install watchdog
    print_message "Installing watchdog..."
    pip install watchdog
    
    # Deactivate virtual environment
    deactivate
}

# Function to install dependencies on Linux
install_linux() {
    print_message "Installing dependencies for Linux..."
    
    # Detect package manager
    if command_exists apt-get; then
        # Debian/Ubuntu
        print_message "Using apt package manager..."
        sudo apt-get update
        sudo apt-get install -y rclone python3 python3-pip python3-venv
    elif command_exists dnf; then
        # Fedora
        print_message "Using dnf package manager..."
        sudo dnf install -y rclone python3 python3-pip python3-virtualenv
    elif command_exists pacman; then
        # Arch Linux
        print_message "Using pacman package manager..."
        sudo pacman -S --noconfirm rclone python python-pip python-virtualenv
    else
        print_error "Unsupported Linux distribution. Please install rclone and Python manually."
        exit 1
    fi
    
    # Check rclone version for bisync support
    RCLONE_VERSION=$(rclone version | grep -oP 'rclone v\K[0-9]+\.[0-9]+\.[0-9]+')
    if [[ "$(echo "$RCLONE_VERSION 1.58.0" | awk '{print ($1 < $2)}')" -eq 1 ]]; then
        print_warning "Your rclone version ($RCLONE_VERSION) is older than 1.58.0 which is required for bisync."
        print_message "Please update rclone to version 1.58.0 or newer."
        print_message "You can download it from: https://rclone.org/downloads/"
    fi
    
    # Setup virtual environment
    setup_virtual_env
    
    # Install watchdog
    print_message "Installing watchdog..."
    pip install watchdog
    
    # Deactivate virtual environment
    deactivate
}

# Function to install dependencies on Windows
install_windows() {
    print_message "Installing dependencies for Windows..."
    
    # Check if Chocolatey is installed
    if ! command_exists choco; then
        print_message "Installing Chocolatey..."
        powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    fi
    
    # Install rclone
    if ! command_exists rclone; then
        print_message "Installing rclone..."
        choco install rclone -y
    else
        # Check rclone version for bisync support
        RCLONE_VERSION=$(rclone version | grep -oP 'rclone v\K[0-9]+\.[0-9]+\.[0-9]+')
        if [[ "$(echo "$RCLONE_VERSION 1.58.0" | awk '{print ($1 < $2)}')" -eq 1 ]]; then
            print_warning "Your rclone version ($RCLONE_VERSION) is older than 1.58.0 which is required for bisync."
            print_message "Updating rclone..."
            choco upgrade rclone -y
        fi
    fi
    
    # Install Python
    if ! command_exists python; then
        print_message "Installing Python..."
        choco install python -y
    fi
    
    # Setup virtual environment
    setup_virtual_env
    
    # Install watchdog
    print_message "Installing watchdog..."
    pip install watchdog
    
    # Deactivate virtual environment
    deactivate
}

# Function to setup rclone
setup_rclone() {
    print_message "Setting up rclone..."
    
    # Check if rclone is installed
    if ! command_exists rclone; then
        print_error "rclone is not installed. Please run the installation part of this script first."
        exit 1
    fi
    
    # Check rclone version for bisync support
    RCLONE_VERSION=$(rclone version | grep -oP 'rclone v\K[0-9]+\.[0-9]+\.[0-9]+')
    if [[ "$(echo "$RCLONE_VERSION 1.58.0" | awk '{print ($1 < $2)}')" -eq 1 ]]; then
        print_error "Your rclone version ($RCLONE_VERSION) is older than 1.58.0 which is required for bisync."
        print_message "Please update rclone to version 1.58.0 or newer."
        print_message "You can download it from: https://rclone.org/downloads/"
        exit 1
    fi
    
    # Create rclone config directory if it doesn't exist
    mkdir -p "$HOME/.rclone"
    
    # Check if rclone is already configured
    if [ -f "$HOME/.rclone/rclone.conf" ]; then
        print_warning "rclone is already configured. Do you want to reconfigure it? (y/n)"
        read -r answer
        if [ "$answer" != "y" ]; then
            print_message "Skipping rclone configuration."
            return
        fi
    fi
    
    # Create Google Drive remote
    print_message "Creating Google Drive remote..."
    rclone config create gdrive drive
    
    # Create encrypted remote
    print_message "Creating encrypted remote..."
    rclone config create gdrive_encrypted crypt remote=gdrive:
    
    print_message "rclone setup completed!"
    print_message "Note: You may need to authenticate with Google Drive when you first use rclone."
    print_message "Run 'rclone lsd gdrive:' to test the connection and authenticate if needed."
}

# Main installation process
main() {
    print_message "Starting setup process..."
    
    # Parse command line arguments
    INSTALL_DEPS=true
    SETUP_RCLONE=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --rclone-only)
                INSTALL_DEPS=false
                SETUP_RCLONE=true
                shift
                ;;
            --deps-only)
                INSTALL_DEPS=true
                SETUP_RCLONE=false
                shift
                ;;
            --all)
                INSTALL_DEPS=true
                SETUP_RCLONE=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                print_message "Usage: $0 [--rclone-only|--deps-only|--all]"
                exit 1
                ;;
        esac
    done
    
    # If no options specified, do both
    if [ "$INSTALL_DEPS" = false ] && [ "$SETUP_RCLONE" = false ]; then
        INSTALL_DEPS=true
        SETUP_RCLONE=true
    fi
    
    # Install dependencies if requested
    if [ "$INSTALL_DEPS" = true ]; then
        # Detect OS and install dependencies
        OS=$(detect_os)
        case $OS in
            macos)
                install_macos
                ;;
            linux)
                install_linux
                ;;
            windows)
                install_windows
                ;;
            *)
                print_error "Unsupported operating system"
                exit 1
                ;;
        esac
        
        # Make scripts executable
        print_message "Making scripts executable..."
        chmod +x sync.sh bidirectional_sync.sh monitor.sh
        
        # Create necessary directories
        print_message "Creating necessary directories..."
        mkdir -p "$HOME/.rclone"
    fi
    
    # Setup rclone if requested
    if [ "$SETUP_RCLONE" = true ]; then
        setup_rclone
    fi
    
    print_message "Setup completed successfully!"
    print_message "Next steps:"
    echo "1. Use './sync.sh' for one-way sync"
    echo "2. Use './bidirectional_sync.sh' for bidirectional sync"
    echo "3. Use './monitor.sh' to monitor a folder and sync on changes"
}

# Run main function
main "$@" 