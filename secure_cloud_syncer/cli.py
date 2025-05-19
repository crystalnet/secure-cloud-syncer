#!/usr/bin/env python3
"""
Command-line interface for Secure Cloud Syncer.
This module provides the CLI for managing sync configurations and the sync service.
"""

import os
import sys
import json
import logging
import argparse
import signal
import psutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
import time

from .sync import one_way, bidirectional, monitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser("~/.rclone/scs.log"))
    ]
)
logger = logging.getLogger("secure_cloud_syncer.cli")

CONFIG_FILE = os.path.expanduser("~/.rclone/scs_config.json")
PID_FILE = os.path.expanduser("~/.rclone/scs_manager.pid")

def load_config() -> Dict[str, Any]:
    """Load the configuration file."""
    if not os.path.exists(CONFIG_FILE):
        return {"syncs": {}}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return {"syncs": {}}

def save_config(config: Dict[str, Any]) -> None:
    """Save the configuration file."""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        sys.exit(1)

def get_running_syncs() -> Dict[str, int]:
    """Get a dictionary of running sync processes."""
    if not os.path.exists(PID_FILE):
        return {}
    
    try:
        with open(PID_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_running_syncs(running_syncs: Dict[str, int]) -> None:
    """Save the running sync processes."""
    try:
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        with open(PID_FILE, 'w') as f:
            json.dump(running_syncs, f)
    except Exception as e:
        logger.error(f"Error saving running syncs: {e}")
        raise

def is_process_running(pid: int) -> bool:
    """Check if a process is running."""
    try:
        process = psutil.Process(pid)
        return process.is_running() and process.name().startswith('python')
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

def add_sync(name, local_dir, remote_dir, mode="one-way", exclude_resource_forks=True, debounce_time=5):
    """Add a new sync configuration."""
    if not os.path.exists(local_dir):
        logger.error(f"Local directory does not exist: {local_dir}")
        sys.exit(1)
    
    if not os.path.isdir(local_dir):
        logger.error(f"Local path is not a directory: {local_dir}")
        sys.exit(1)
    
    config = load_config()
    
    if name in config["syncs"]:
        logger.error(f"Sync configuration '{name}' already exists")
        sys.exit(1)
    
    config["syncs"][name] = {
        "name": name,
        "local_dir": local_dir,
        "remote_dir": remote_dir,
        "mode": mode,
        "exclude_resource_forks": exclude_resource_forks,
        "debounce_time": debounce_time
    }
    
    save_config(config)
    logger.info(f"Added sync configuration '{name}'")

def list_syncs():
    """List all sync configurations."""
    config = load_config()
    
    if not config["syncs"]:
        print("No sync configurations found")
        return
    
    print("\nSync Configurations:")
    print("-" * 80)
    for name, sync_config in config["syncs"].items():
        print(f"Name: {name}")
        print(f"Local Directory: {sync_config['local_dir']}")
        print(f"Remote Directory: {sync_config['remote_dir']}")
        print(f"Mode: {sync_config['mode']}")
        print(f"Exclude Resource Forks: {sync_config['exclude_resource_forks']}")
        if sync_config['mode'] == 'monitor':
            print(f"Debounce Time: {sync_config['debounce_time']} seconds")
        print("-" * 80)

def remove_sync(name):
    """Remove a sync configuration."""
    config = load_config()
    
    if name not in config["syncs"]:
        logger.error(f"Sync configuration '{name}' does not exist")
        sys.exit(1)
    
    del config["syncs"][name]
    save_config(config)
    logger.info(f"Removed sync configuration '{name}'")

def start_sync(args) -> None:
    """Start a sync configuration."""
    config = load_config()
    running_syncs = get_running_syncs()
    
    if args.name not in config["syncs"]:
        print(f"Error: Sync configuration '{args.name}' not found")
        sys.exit(1)
    
    # Check if already running
    if args.name in running_syncs and is_process_running(running_syncs[args.name]):
        print(f"Error: Sync configuration '{args.name}' is already running")
        sys.exit(1)
    
    sync = config["syncs"][args.name]
    
    try:
        # Start the sync in a new process
        if sync["mode"] == "one-way":
            process = one_way.sync_directory(
                sync["local_dir"],
                sync["remote_dir"],
                sync["exclude_resource_forks"],
                background=True
            )
        elif sync["mode"] == "bidirectional":
            process = bidirectional.sync_bidirectional(
                sync["local_dir"],
                sync["remote_dir"],
                sync["exclude_resource_forks"],
                background=True
            )
        elif sync["mode"] == "monitor":
            process = monitor.start_monitoring(
                sync["local_dir"],
                sync["remote_dir"],
                sync["exclude_resource_forks"],
                sync["debounce_time"],
                background=True
            )
        
        # Save the process ID
        running_syncs[args.name] = process.pid
        save_running_syncs(running_syncs)
        print(f"Started sync configuration '{args.name}'")
        
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        sys.exit(1)

def stop_sync(args) -> None:
    """Stop a sync configuration."""
    running_syncs = get_running_syncs()
    
    if args.name not in running_syncs:
        print(f"Error: Sync configuration '{args.name}' is not running")
        sys.exit(1)
    
    pid = running_syncs[args.name]
    try:
        process = psutil.Process(pid)
        process.terminate()
        process.wait(timeout=5)  # Wait up to 5 seconds for the process to terminate
        del running_syncs[args.name]
        save_running_syncs(running_syncs)
        print(f"Stopped sync configuration '{args.name}'")
    except psutil.NoSuchProcess:
        print(f"Sync configuration '{args.name}' was already stopped")
        del running_syncs[args.name]
        save_running_syncs(running_syncs)
    except psutil.TimeoutExpired:
        process.kill()  # Force kill if it doesn't terminate
        del running_syncs[args.name]
        save_running_syncs(running_syncs)
        print(f"Force stopped sync configuration '{args.name}'")

def restart_sync(args) -> None:
    """Restart a sync configuration."""
    # Stop the sync if it's running
    try:
        stop_sync(args)
    except SystemExit:
        pass  # Ignore if the sync wasn't running
    
    # Start the sync
    start_sync(args)

def is_service_running():
    """Check if the sync service is running."""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    except Exception:
        return False

def start_service():
    """Start the sync service."""
    if is_service_running():
        logger.error("Sync service is already running")
        sys.exit(1)
    
    try:
        # Start the service in the background
        subprocess.Popen([sys.executable, "-m", "secure_cloud_syncer.manager"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        logger.info("Sync service started")
    except Exception as e:
        logger.error(f"Error starting sync service: {e}")
        sys.exit(1)

def stop_service():
    """Stop the sync service."""
    if not is_service_running():
        logger.error("Sync service is not running")
        sys.exit(1)
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGTERM to the service
        os.kill(pid, 15)  # SIGTERM
        
        # Wait for the service to stop
        for _ in range(10):  # Wait up to 10 seconds
            if not is_service_running():
                break
            import time
            time.sleep(1)
        else:
            # If service didn't stop, force kill
            os.kill(pid, 9)  # SIGKILL
        
        logger.info("Sync service stopped")
    except Exception as e:
        logger.error(f"Error stopping sync service: {e}")
        sys.exit(1)

def reload_service():
    """Reload the sync service configuration."""
    if not is_service_running():
        logger.error("Sync service is not running")
        sys.exit(1)
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Send SIGHUP to the service
        os.kill(pid, 1)  # SIGHUP
        logger.info("Sync service configuration reloaded")
    except Exception as e:
        logger.error(f"Error reloading sync service: {e}")
        sys.exit(1)

def setup_rclone():
    """Set up rclone with cloud storage authentication and encryption."""
    try:
        # Check if rclone is installed
        subprocess.run(['rclone', 'version'], capture_output=True, check=True)
        
        # Create rclone config directory if it doesn't exist
        config_dir = os.path.expanduser('~/.rclone')
        os.makedirs(config_dir, exist_ok=True)
        
        print("\n=== Cloud Storage Setup ===")
        print("Choose your cloud storage provider:")
        print("1. Google Drive")
        print("2. OneDrive")
        print("3. Dropbox")
        print("4. Custom Setup")
        print("q. Quit")
        
        choice = input("\nEnter your choice (1-4, or q to quit): ").strip().lower()
        
        if choice == 'q':
            print("Setup cancelled.")
            sys.exit(0)
        
        # Ask about encryption preferences
        print("\n=== Encryption Settings ===")
        print("Choose your encryption preferences:")
        print("1. Standard (preserve file and folder names)")
        print("2. Obfuscate (encrypt file and folder names)")
        print("3. Custom encryption settings")
        
        enc_choice = input("\nEnter your choice (1-3): ").strip()
        
        # Set encryption parameters based on choice
        if enc_choice == '1':  # Standard
            filename_encryption = 'standard'
            directory_name_encryption = 'false'
        elif enc_choice == '2':  # Obfuscate
            filename_encryption = 'standard'
            directory_name_encryption = 'true'
        elif enc_choice == '3':  # Custom
            print("\nCustom encryption settings:")
            print("Filename encryption options:")
            print("1. standard - Encrypt the filenames")
            print("2. obfuscate - Very simple filename obfuscation")
            print("3. off - Don't encrypt the file names")
            filename_enc = input("Choose filename encryption (1-3): ").strip()
            filename_encryption = {
                '1': 'standard',
                '2': 'obfuscate',
                '3': 'off'
            }.get(filename_enc, 'standard')
            
            print("\nDirectory name encryption:")
            print("1. true - Encrypt directory names")
            print("2. false - Don't encrypt directory names")
            dir_enc = input("Choose directory encryption (1-2): ").strip()
            directory_name_encryption = 'true' if dir_enc == '1' else 'false'
        else:
            print("Invalid choice, using standard encryption.")
            filename_encryption = 'standard'
            directory_name_encryption = 'false'
        
        # Get encryption password with confirmation
        print("\n=== Encryption Settings ===")
        print("Please enter a password for encryption.")
        print("This password will be used to encrypt and decrypt your files.")
        print("Make sure to remember this password - it cannot be recovered if lost!")
        while True:
            password = input("\nEnter encryption password: ").strip()
            password2 = input("Confirm encryption password: ").strip()
            if password == password2:
                break
            print("\n❌ Passwords do not match. Please try again.")
        
        # Generate a random salt
        import secrets
        import string
        salt = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        print("\nA secure random salt has been generated for encryption.")
        print("This salt will be saved with your configuration.")
        print("Salt:", salt)
        
        if choice == '1':  # Google Drive
            print("\nSetting up Google Drive...")
            print("A browser window will open for Google Drive authentication.")
            
            # Ask about team drive
            print("\nDo you want to use a Google Workspace (formerly G Suite) team drive?")
            print("1. No, use my personal Google Drive")
            print("2. Yes, use a team drive")
            team_drive_choice = input("\nEnter your choice (1-2): ").strip()
            
            # Create gdrive remote
            if team_drive_choice == '2':
                # For team drive, we need the team drive ID
                print("\nPlease enter your team drive ID.")
                print("You can find this in the URL when viewing your team drive:")
                print("https://drive.google.com/drive/folders/TEAM_DRIVE_ID")
                team_drive_id = input("\nEnter team drive ID: ").strip()
                
                result = subprocess.run(['rclone', 'config', 'create', 'gdrive', 'drive', 
                              'scope', 'drive', 'root_folder_id', team_drive_id, 
                              'service_account_file', '', 'advanced_config', 'n',
                              'auto_config', 'y'], 
                              capture_output=True, text=True)
            else:
                # For personal drive
                result = subprocess.run(['rclone', 'config', 'create', 'gdrive', 'drive', 
                              'scope', 'drive', 'root_folder_id', 'root', 
                              'service_account_file', '', 'advanced_config', 'n',
                              'auto_config', 'y'], 
                              capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"\n❌ Error creating Google Drive remote:")
                print(result.stderr)
                sys.exit(1)
            
            # Create encrypted remote
            result = subprocess.run(['rclone', 'config', 'create', 'gdrive-crypt', 'crypt',
                          'remote', 'gdrive:', 'filename_encryption', filename_encryption,
                          'directory_name_encryption', directory_name_encryption,
                          'password', password, 'salt', salt,
                          'password2', password,  # Required for crypt remote
                          'show_mapping', 'false'], 
                          capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\n❌ Error creating encrypted remote:")
                print(result.stderr)
                sys.exit(1)
            
        elif choice == '2':  # OneDrive
            print("\nSetting up OneDrive...")
            print("A browser window will open for OneDrive authentication.")
            # Create onedrive remote
            result = subprocess.run(['rclone', 'config', 'create', 'onedrive', 'onedrive',
                          'region', 'global', 'advanced_config', 'n', 
                          'auto_config', 'y'], 
                          capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\n❌ Error creating OneDrive remote:")
                print(result.stderr)
                sys.exit(1)
            
            # Create encrypted remote
            result = subprocess.run(['rclone', 'config', 'create', 'onedrive-crypt', 'crypt',
                          'remote', 'onedrive:', 'filename_encryption', filename_encryption,
                          'directory_name_encryption', directory_name_encryption,
                          'password', password, 'salt', salt,
                          'password2', password,  # Required for crypt remote
                          'show_mapping', 'false'], 
                          capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\n❌ Error creating encrypted remote:")
                print(result.stderr)
                sys.exit(1)
            
        elif choice == '3':  # Dropbox
            print("\nSetting up Dropbox...")
            print("A browser window will open for Dropbox authentication.")
            # Create dropbox remote
            result = subprocess.run(['rclone', 'config', 'create', 'dropbox', 'dropbox',
                          'advanced_config', 'n', 'auto_config', 'y'], 
                          capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\n❌ Error creating Dropbox remote:")
                print(result.stderr)
                sys.exit(1)
            
            # Create encrypted remote
            result = subprocess.run(['rclone', 'config', 'create', 'dropbox-crypt', 'crypt',
                          'remote', 'dropbox:', 'filename_encryption', filename_encryption,
                          'directory_name_encryption', directory_name_encryption,
                          'password', password, 'salt', salt,
                          'password2', password,  # Required for crypt remote
                          'show_mapping', 'false'], 
                          capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\n❌ Error creating encrypted remote:")
                print(result.stderr)
                sys.exit(1)
            
        elif choice == '4':  # Custom Setup
            print("\nStarting custom rclone configuration...")
            print("Please follow the prompts to set up your cloud storage.")
            print("For encryption, you'll need to set up a second remote with the '-crypt' suffix")
            print("and choose 'crypt' as the storage type.")
            subprocess.run(['rclone', 'config'], check=True)
            
        else:
            print("Invalid choice. Please try again.")
            return setup_rclone()
        
        # Verify configuration
        remote_name = {
            '1': 'gdrive',
            '2': 'onedrive',
            '3': 'dropbox'
        }.get(choice)
        
        if remote_name:
            try:
                # For Google Drive, we need to use a different verification method
                if remote_name == 'gdrive':
                    # Try to create a test directory
                    test_dir = f"scs-test-{int(time.time())}"
                    result = subprocess.run(['rclone', 'mkdir', f'{remote_name}:{test_dir}'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        # Clean up the test directory
                        subprocess.run(['rclone', 'rmdir', f'{remote_name}:{test_dir}'], 
                                     capture_output=True, text=True)
                        print(f"\n✅ {remote_name.capitalize()} configuration successful!")
                        print("\nNext steps:")
                        print("1. Add a folder to sync: scs add <name> <local-path> --remote-dir <remote-path>")
                        print("2. Start the sync service: scs service start")
                    else:
                        print(f"\n❌ {remote_name.capitalize()} configuration failed:")
                        print(result.stderr)
                        sys.exit(1)
                else:
                    # For other providers, use the original ls method
                    result = subprocess.run(['rclone', 'ls', f'{remote_name}:'], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"\n✅ {remote_name.capitalize()} configuration successful!")
                        print("\nNext steps:")
                        print("1. Add a folder to sync: scs add <name> <local-path> --remote-dir <remote-path>")
                        print("2. Start the sync service: scs service start")
                    else:
                        print(f"\n❌ {remote_name.capitalize()} configuration failed:")
                        print(result.stderr)
                        sys.exit(1)
            except subprocess.CalledProcessError as e:
                print(f"\n❌ {remote_name.capitalize()} configuration failed:")
                print(e.stderr)
                sys.exit(1)
        else:
            print("\n✅ Custom configuration completed!")
            print("\nNext steps:")
            print("1. Add a folder to sync: scs add <name> <local-path> --remote-dir <remote-path>")
            print("2. Start the sync service: scs service start")
            
    except FileNotFoundError:
        print("\n❌ rclone binary not found!")
        print("Please install rclone first:")
        print("  macOS: brew install rclone")
        print("  Linux: curl https://rclone.org/install.sh | sudo bash")
        print("  Windows: Download from https://rclone.org/downloads/")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error during rclone setup: {e}")
        if hasattr(e, 'stderr'):
            print(e.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description='Secure Cloud Syncer CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Set up rclone with Google Drive')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new sync configuration')
    add_parser.add_argument('name', help='Name of the sync configuration')
    add_parser.add_argument('local_path', help='Local path to sync')
    add_parser.add_argument('--remote-dir', required=True, help='Remote directory path')
    add_parser.add_argument('--mode', choices=['upload', 'download', 'bidirectional'], 
                          default='bidirectional', help='Sync mode')
    
    # List command
    subparsers.add_parser('list', help='List all sync configurations')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a sync configuration')
    remove_parser.add_argument('name', help='Name of the sync configuration to remove')
    
    # Service commands
    service_parser = subparsers.add_parser('service', help='Manage the sync service')
    service_subparsers = service_parser.add_subparsers(dest='service_command', help='Service commands')
    service_subparsers.add_parser('start', help='Start the sync service')
    service_subparsers.add_parser('stop', help='Stop the sync service')
    service_subparsers.add_parser('status', help='Check service status')
    
    args = parser.parse_args()
    
    if args.command == 'setup':
        setup_rclone()
    elif args.command == 'add':
        add_sync(args.name, args.local_path, args.remote_dir, args.mode)
    elif args.command == 'list':
        list_syncs()
    elif args.command == 'remove':
        remove_sync(args.name)
    elif args.command == 'service':
        if args.service_command == 'start':
            start_service()
        elif args.service_command == 'stop':
            stop_service()
        elif args.service_command == 'status':
            check_service_status()
        else:
            service_parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 