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
    fi
    
    # Install Python if not present (needed for rclonesync)
    if ! command_exists python3; then
        print_message "Installing Python..."
        brew install python
    fi
    
    # Install pip if not present
    if ! command_exists pip3; then
        print_message "Installing pip..."
        python3 -m ensurepip --upgrade
    fi
    
    # Install rclonesync
    print_message "Installing rclonesync..."
    pip3 install rclonesync
}

# Function to install dependencies on Linux
install_linux() {
    print_message "Installing dependencies for Linux..."
    
    # Detect package manager
    if command_exists apt-get; then
        # Debian/Ubuntu
        print_message "Using apt package manager..."
        sudo apt-get update
        sudo apt-get install -y rclone python3 python3-pip
    elif command_exists dnf; then
        # Fedora
        print_message "Using dnf package manager..."
        sudo dnf install -y rclone python3 python3-pip
    elif command_exists pacman; then
        # Arch Linux
        print_message "Using pacman package manager..."
        sudo pacman -S --noconfirm rclone python python-pip
    else
        print_error "Unsupported Linux distribution. Please install rclone and Python manually."
        exit 1
    fi
    
    # Install rclonesync
    print_message "Installing rclonesync..."
    pip3 install rclonesync
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
    fi
    
    # Install Python
    if ! command_exists python; then
        print_message "Installing Python..."
        choco install python -y
    fi
    
    # Install rclonesync
    print_message "Installing rclonesync..."
    pip install rclonesync
}

# Main installation process
main() {
    print_message "Starting setup process..."
    
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
    chmod +x sync.sh bidirectional_sync.sh setup_rclone.sh
    
    # Create necessary directories
    print_message "Creating necessary directories..."
    mkdir -p "$HOME/.rclone"
    
    print_message "Setup completed successfully!"
    print_message "Next steps:"
    echo "1. Run './setup_rclone.sh' to configure rclone with your Google Drive"
    echo "2. Use './sync.sh' for one-way sync"
    echo "3. Use './bidirectional_sync.sh' for bidirectional sync"
}

# Run main function
main 