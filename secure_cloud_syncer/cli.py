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
import multiprocessing

from .sync import one_way, bidirectional, monitor

# Configure logging
class SimpleFormatter(logging.Formatter):
    """A simple formatter that only shows the message for INFO and below."""
    def format(self, record):
        if record.levelno <= logging.INFO:
            return record.getMessage()
        return f"{record.levelname}: {record.getMessage()}"

# Set up logging
logging.basicConfig(level=logging.INFO)

# Create console handler with simple format
console_handler = logging.StreamHandler()
console_handler.setFormatter(SimpleFormatter())

# Create file handler with detailed format
file_handler = logging.FileHandler(os.path.expanduser("~/.rclone/scs.log"))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Configure our package logger
logger = logging.getLogger("secure_cloud_syncer.cli")
logger.setLevel(logging.INFO)
logger.propagate = False  # Prevent propagation to root logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

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
            data = json.load(f)
            # Ensure we have a dictionary
            if not isinstance(data, dict):
                logger.warning("Invalid PID file format, initializing new PID file")
                return {}
            return data
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in PID file, initializing new PID file")
        return {}
    except Exception as e:
        logger.warning(f"Error reading PID file: {e}, initializing new PID file")
        return {}

def save_running_syncs(running_syncs: Dict[str, int]) -> None:
    """Save the running sync processes."""
    try:
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        # Ensure we have a valid dictionary
        if not isinstance(running_syncs, dict):
            running_syncs = {}
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

def add_sync(name, local_dir, remote_dir, mode="bidirectional", exclude_resource_forks=True, debounce_time=5):
    """Add a new sync configuration."""
    # Convert paths to platform-specific format
    local_dir = os.path.normpath(local_dir)
    
    # Verify local directory
    if not os.path.exists(local_dir):
        logger.error(f"Local directory does not exist: {local_dir}")
        sys.exit(1)
    
    if not os.path.isdir(local_dir):
        logger.error(f"Local path is not a directory: {local_dir}")
        sys.exit(1)
    
    # Verify remote path format
    if not remote_dir.startswith(('gdrive:', 'gdrive-crypt:', 'onedrive:', 'onedrive-crypt:', 'dropbox:', 'dropbox-crypt:')):
        logger.error("Remote directory must start with the remote name (e.g., 'gdrive:', 'gdrive-crypt:', 'onedrive:', 'onedrive-crypt:', 'dropbox:', 'dropbox-crypt:')")
        sys.exit(1)
    
    # Split remote path into remote name and path
    remote_name, remote_path = remote_dir.split(':', 1)
    if not remote_path:
        logger.error("Remote path cannot be empty")
        sys.exit(1)
    
    # Normalize remote path to use forward slashes
    remote_path = remote_path.replace('\\', '/')
    
    # For drive.file scope, ensure path is under rclone root
    if remote_name == 'gdrive':
        try:
            result = subprocess.run(['rclone', 'config', 'show', remote_name], 
                                  capture_output=True, text=True)
            if 'scope = drive.file' in result.stdout:
                config = load_config()
                rclone_root = config.get('rclone_root', 'secureCloudSyncer')
                if not remote_path.startswith(f"{rclone_root}/"):
                    logger.error(f"With 'drive.file' scope, all paths must be under '{rclone_root}/'")
                    logger.error(f"Please use a path like: gdrive:{rclone_root}/your-folder")
                    sys.exit(1)
        except Exception as e:
            logger.error(f"Error checking rclone configuration: {e}")
            sys.exit(1)
    
    # Verify rclone configuration
    try:
        # Check if remote exists
        result = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True, check=True)
        if f"{remote_name}:" not in result.stdout:
            logger.error(f"Remote '{remote_name}' not found in rclone configuration")
            sys.exit(1)
        
        # Try to create a test file in the remote directory
        test_file = f"scs-test-{int(time.time())}.txt"
        test_content = "This is a test file created by Secure Cloud Syncer"
        test_file_path = os.path.join(local_dir, test_file)
        
        logger.debug(f"Creating test file: {test_file_path}")
        # Create test file locally
        with open(test_file_path, 'w') as f:
            f.write(test_content)
        
        # Try to copy the test file to remote
        remote_path = remote_path.rstrip('/')  # Remove trailing slash
        logger.debug(f"Copying test file to remote: {remote_name}:{remote_path}/{test_file}")
        result = subprocess.run(['rclone', 'copy', test_file_path, f"{remote_name}:{remote_path}"], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Cannot write to {remote_dir}")
            logger.error("Error:", result.stderr)
            sys.exit(1)
        
        logger.info("Successfully verified write access to remote directory")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error verifying rclone configuration: {e}")
        if hasattr(e, 'stderr'):
            logger.error(e.stderr)
        sys.exit(1)
    finally:
        # Clean up test file from remote
        remote_path = remote_path.rstrip('/')  # Remove trailing slash
        logger.debug(f"Cleaning up test file from remote: {remote_name}:{remote_path}/{test_file}")
        try:
            # Use rclone deletefile with the correct path format
            result = subprocess.run(['rclone', 'deletefile', f"{remote_name}:{remote_path}/{test_file}"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                logger.debug(f"Successfully cleaned up test file from remote: {remote_path}/{test_file}")
            else:
                logger.warning(f"Failed to clean up test file from remote: {result.stderr}")
        except Exception as e:
            logger.warning(f"Error during remote cleanup: {e}")
        
        # Clean up local test file
        logger.debug(f"Cleaning up local test file: {test_file_path}")
        try:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
                logger.debug(f"Successfully cleaned up local test file: {test_file_path}")
            else:
                logger.warning(f"Local test file not found: {test_file_path}")
        except Exception as e:
            logger.warning(f"Error during local cleanup: {e}")
    
    config = load_config()
    
    if name in config["syncs"]:
        logger.error(f"Sync configuration '{name}' already exists")
        sys.exit(1)
    
    # Add the sync configuration with status
    config["syncs"][name] = {
        "name": name,
        "local_dir": local_dir,
        "remote_dir": remote_dir,
        "mode": mode,  # 'bidirectional' or 'upload'
        "exclude_resource_forks": exclude_resource_forks,
        "debounce_time": debounce_time,
        "status": "active"  # Can be: active, paused
    }
    
    save_config(config)
    logger.info(f"Added sync configuration '{name}'")
    logger.info(f"Local directory: {local_dir}")
    logger.info(f"Remote directory: {remote_dir}")
    logger.info(f"Mode: {mode}")
    
    # Ensure service is running
    if not is_service_running():
        logger.info("Starting sync service...")
        start_service()
        # Give the service a moment to start
        time.sleep(2)
    
    # Tell the service to start the sync
    try:
        # Send SIGHUP to the service to reload configuration
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        logger.info(f"Started sync '{name}'")
    except Exception as e:
        logger.error(f"Error starting sync: {e}")
        sys.exit(1)

def list_syncs():
    """List all sync configurations."""
    config = load_config()
    
    if not config["syncs"]:
        print("No sync configurations found")
        return
    
    # Separate active and paused syncs
    active_syncs = {}
    paused_syncs = {}
    
    for name, sync_config in config["syncs"].items():
        if sync_config.get('status') == 'paused':
            paused_syncs[name] = sync_config
        else:
            active_syncs[name] = sync_config
    
    # Print active syncs
    if active_syncs:
        print("\nActive Sync Configurations:")
        print("-" * 80)
        for name, sync_config in active_syncs.items():
            print(f"Name: {name}")
            print(f"Local Directory: {sync_config['local_dir']}")
            print(f"Remote Directory: {sync_config['remote_dir']}")
            print(f"Mode: {sync_config['mode']}")
            print(f"Exclude Resource Forks: {sync_config['exclude_resource_forks']}")
            if sync_config['mode'] == 'monitor':
                print(f"Debounce Time: {sync_config['debounce_time']} seconds")
            print("-" * 80)
    else:
        print("\nNo active sync configurations")
    
    # Print paused syncs
    if paused_syncs:
        print("\nPaused Sync Configurations:")
        print("-" * 80)
        for name, sync_config in paused_syncs.items():
            print(f"Name: {name}")
            print(f"Local Directory: {sync_config['local_dir']}")
            print(f"Remote Directory: {sync_config['remote_dir']}")
            print(f"Mode: {sync_config['mode']}")
            print(f"Exclude Resource Forks: {sync_config['exclude_resource_forks']}")
            if sync_config['mode'] == 'monitor':
                print(f"Debounce Time: {sync_config['debounce_time']} seconds")
            print("-" * 80)
    else:
        print("\nNo paused sync configurations")

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
    
    if args.name not in config["syncs"]:
        print(f"Error: Sync configuration '{args.name}' not found")
        sys.exit(1)
    
    # Ensure service is running
    if not is_service_running():
        logger.info("Starting sync service...")
        start_service()
        # Give the service a moment to start
        time.sleep(2)
    
    # Tell the service to start the sync
    try:
        # Send SIGHUP to the service to reload configuration
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        logger.info(f"Started sync '{args.name}'")
    except Exception as e:
        logger.error(f"Error starting sync: {e}")
        sys.exit(1)

def stop_sync(args) -> None:
    """Stop a sync configuration."""
    config = load_config()
    
    if args.name not in config["syncs"]:
        logger.info(f"Sync configuration '{args.name}' does not exist")
        return
    
    # Ensure service is running
    if not is_service_running():
        logger.info("Sync service is not running")
        return
    
    try:
        # Send SIGHUP to the service to reload configuration
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        logger.info(f"Stopped sync configuration '{args.name}'")
    except Exception as e:
        logger.error(f"Error stopping sync: {e}")
        sys.exit(1)

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
            if os.name == 'nt':  # Windows
                import psutil
                return psutil.pid_exists(pid)
            else:  # Unix
                os.kill(pid, 0)
                return True
        except (OSError, psutil.NoSuchProcess):
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
        if os.name == 'nt':  # Windows
            # Use pythonw.exe to run without console window
            python_exe = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            subprocess.Popen([python_exe, "-m", "secure_cloud_syncer.manager"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:  # Unix
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
        
        if os.name == 'nt':  # Windows
            import psutil
            try:
                process = psutil.Process(pid)
                process.terminate()
                process.wait(timeout=10)  # Wait up to 10 seconds
            except psutil.NoSuchProcess:
                pass
            except psutil.TimeoutExpired:
                process.kill()  # Force kill if termination times out
        else:  # Unix
            # Send SIGTERM to the service
            os.kill(pid, 15)  # SIGTERM
            
            # Wait for the service to stop
            for _ in range(10):  # Wait up to 10 seconds
                if not is_service_running():
                    break
                time.sleep(1)
            else:
                # If service didn't stop, force kill
                os.kill(pid, 9)  # SIGKILL
        
        logger.info("Sync service stopped")
    except Exception as e:
        logger.error(f"Error stopping sync service: {e}")
        sys.exit(1)

def restart_service():
    """Restart the sync service."""
    stop_service()
    start_service()

def reload_service():
    """Reload the sync service configuration."""
    if not is_service_running():
        logger.error("Sync service is not running")
        sys.exit(1)
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        if os.name == 'nt':  # Windows
            # On Windows, we need to stop and restart the service
            stop_service()
            start_service()
        else:  # Unix
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
        print("Choose how to handle file names:")
        print("1. standard - Full encryption of file names (most private)")
        print("2. obfuscate - Simple filename obfuscation (moderate privacy)")
        print("3. off - No encryption of file names (most convenient)")
        filename_enc = input("\nEnter your choice (1-3): ").strip()
        filename_encryption = {
            '1': 'standard',
            '2': 'obfuscate',
            '3': 'off'
        }.get(filename_enc, 'standard')
        
        print("\nChoose how to handle folder names:")
        print("1. Encrypt folder names - Folder names will be encrypted on the remote (most private)")
        print("2. Don't encrypt folder names - Folder names will be stored as-is (more convenient)")
        dir_enc = input("\nEnter your choice (1-2): ").strip()
        directory_name_encryption = {
            '1': 'true',
            '2': 'false'
        }.get(dir_enc, 'true')
        
        # Save encryption settings to config for future reference
        config = load_config()
        config['encryption_settings'] = {
            'filename_encryption': filename_encryption,
            'directory_name_encryption': directory_name_encryption
        }
        save_config(config)
        
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
        
        # Provider-specific setup
        provider_info = {
            '1': {
                'name': 'Google Drive',
                'remote': 'gdrive',
                'crypt_remote': 'gdrive-crypt',
                'setup_cmd': ['rclone', 'config', 'create', 'gdrive', 'drive'],
                'scope_prompt': True
            },
            '2': {
                'name': 'OneDrive',
                'remote': 'onedrive',
                'crypt_remote': 'onedrive-crypt',
                'setup_cmd': ['rclone', 'config', 'create', 'onedrive', 'onedrive', 'region', 'global'],
                'scope_prompt': False
            },
            '3': {
                'name': 'Dropbox',
                'remote': 'dropbox',
                'crypt_remote': 'dropbox-crypt',
                'setup_cmd': ['rclone', 'config', 'create', 'dropbox', 'dropbox'],
                'scope_prompt': False
            }
        }
        
        if choice in provider_info:
            provider = provider_info[choice]
            print(f"\nSetting up {provider['name']}...")
            
            # Add scope selection for Google Drive
            if provider['scope_prompt']:
                print("\n=== Google Drive Access Level ===")
                print("Choose the access level for Google Drive:")
                print("1. Full Access (recommended)")
                print("   - Can sync any folder in your Google Drive")
                print("   - No need to share folders with rclone")
                print("   - Less private but more convenient")
                print("\n2. Restricted Access")
                print("   - Can only sync folders created by rclone")
                print("   - More private but less convenient")
                print("   - Cannot sync existing folders unless created by rclone")
                print("   - A root folder will be created for rclone to work with")
                
                scope_choice = input("\nEnter your choice (1-2): ").strip()
                drive_scope = 'drive' if scope_choice == '1' else 'drive.file'
                provider['setup_cmd'].extend(['scope', drive_scope])
            
            # Add common parameters
            provider['setup_cmd'].extend(['advanced_config', 'n', 'auto_config', 'y'])
            
            # Run the setup command
            print(f"\n🔄 Opening browser for {provider['name']} authentication...")
            print("Please complete the authentication in your browser.")
            print("Waiting for authentication to complete...")
            
            result = subprocess.run(provider['setup_cmd'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\n❌ Error creating {provider['name']} remote:")
                print(result.stderr)
                sys.exit(1)
            
            print(f"✅ {provider['name']} authentication completed!")
            
            # Handle restricted access setup
            if provider['scope_prompt'] and drive_scope == 'drive.file':
                print("\n=== Rclone Root Folder Setup ===")
                print("With restricted access, rclone needs a dedicated folder to work with.")
                print("1. Use default folder (recommended)")
                print("   - Creates 'secureCloudSyncer' in your Google Drive root")
                print("   - All syncs will be under this folder")
                print("2. Specify custom folder")
                print("   - Choose your own folder name and location")
                
                folder_choice = input("\nEnter your choice (1-2): ").strip()
                
                if folder_choice == '1':
                    rclone_root = 'secureCloudSyncer'
                else:
                    print("\nEnter the folder path for rclone (e.g., 'MyFolder' or 'Work/rclone'):")
                    print("Note: The folder will be created in your Google Drive root")
                    rclone_root = input("Folder path: ").strip()
                    if not rclone_root:
                        rclone_root = 'secureCloudSyncer'
                        print("Using default folder name: secureCloudSyncer")
                
                print(f"\nCreating root folder '{rclone_root}'...")
                result = subprocess.run(['rclone', 'mkdir', f"{provider['remote']}:{rclone_root}"], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"\n❌ Error creating root folder:")
                    print(result.stderr)
                    sys.exit(1)
                print(f"✅ Created root folder '{rclone_root}' in your {provider['name']}")
                
                # Save the rclone root folder to config for future use
                config = load_config()
                config['rclone_root'] = rclone_root
                save_config(config)
            
            # Create encrypted remote
            result = subprocess.run(['rclone', 'config', 'create', provider['crypt_remote'], 'crypt',
                          'remote', f"{provider['remote']}:", 'filename_encryption', filename_encryption,
                          'directory_name_encryption', directory_name_encryption,
                          'password', password, 'salt', salt,
                          'password2', password,  # Required for crypt remote
                          'show_mapping', 'false'], 
                          capture_output=True, text=True)
            if result.returncode != 0:
                print(f"\n❌ Error creating encrypted remote:")
                print(result.stderr)
                sys.exit(1)
            
            # Verify configuration
            try:
                if provider['scope_prompt'] and drive_scope == 'drive.file':
                    # For restricted access, verify the root folder
                    test_dir = f"{rclone_root}/scs-test-{int(time.time())}"
                    result = subprocess.run(['rclone', 'mkdir', f"{provider['remote']}:{test_dir}"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        # Clean up test directory
                        subprocess.run(['rclone', 'rmdir', f"{provider['remote']}:{test_dir}"], 
                                     capture_output=True, text=True)
                        print(f"\n✅ {provider['name']} configuration successful!")
                else:
                    # For full access, verify basic connectivity
                    result = subprocess.run(['rclone', 'ls', f"{provider['remote']}:"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        print(f"\n✅ {provider['name']} configuration successful!")
                    else:
                        print(f"\n❌ {provider['name']} configuration failed:")
                        print(result.stderr)
                        sys.exit(1)
            except subprocess.CalledProcessError as e:
                print(f"\n❌ {provider['name']} configuration failed:")
                print(e.stderr)
                sys.exit(1)
            
        elif choice == '4':  # Custom Setup
            print("\nStarting custom rclone configuration...")
            print("Please follow the prompts to set up your cloud storage.")
            print("For encryption, you'll need to set up a second remote with the '-crypt' suffix")
            print("and choose 'crypt' as the storage type.")
            subprocess.run(['rclone', 'config'], check=True)
            print("\n✅ Custom configuration completed!")
        else:
            print("Invalid choice. Please try again.")
            return setup_rclone()
        
        # Start the sync service
        if not is_service_running():
            print("\nStarting sync service...")
            start_service()
            print("✅ Sync service started")
        else:
            print("\n✅ Sync service is already running")
        
        # Show next steps at the very end
        print("\nNext steps:")
        print("   - Add a folder to sync: scs add <name> <local-path> --remote-dir <remote-path>")
        if provider['scope_prompt'] and drive_scope == 'drive.file':
            print(f"   Note: Use paths under '{provider['crypt_remote']}:{rclone_root}/' for remote directories")
        
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

def check_service_status():
    """Check the status of the sync service."""
    if is_service_running():
        print("Sync service is running")
    else:
        print("Sync service is not running")

def cleanup_setup():
    """Remove all configurations and created folders from the setup process."""
    print("\n=== Cleaning up Secure Cloud Syncer setup ===")
    
    # Load config to get rclone root folder
    config = load_config()
    rclone_root = config.get('rclone_root', 'secureCloudSyncer')
    
    # Stop the service if it's running
    print("\nStopping sync service...")
    if is_service_running():
        try:
            stop_service()
            print("✅ Stopped sync service")
        except Exception as e:
            print(f"ℹ️ Error stopping service: {e}")
    else:
        print("ℹ️ Service is not running")
    
    # Remove rclone remotes
    print("\nRemoving rclone remotes...")
    remotes = ['gdrive', 'gdrive-crypt', 'onedrive', 'onedrive-crypt', 'dropbox', 'dropbox-crypt']
    for remote in remotes:
        try:
            result = subprocess.run(['rclone', 'config', 'delete', remote], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Removed remote '{remote}'")
            else:
                print(f"ℹ️ Remote '{remote}' not found")
        except Exception as e:
            print(f"ℹ️ Error removing remote '{remote}': {e}")
    
    # Remove Google Drive folder if it exists
    print("\nRemoving Google Drive folder...")
    try:
        result = subprocess.run(['rclone', 'config', 'show', 'gdrive'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and 'scope = drive.file' in result.stdout:
            # Try to remove the folder
            subprocess.run(['rclone', 'purge', f'gdrive:{rclone_root}'], 
                         capture_output=True, text=True)
            print(f"✅ Removed folder '{rclone_root}' from Google Drive")
    except Exception as e:
        print(f"ℹ️ Error removing Google Drive folder: {e}")
    
    # Remove all Secure Cloud Syncer related files
    print("\nRemoving configuration files and logs...")
    rclone_dir = os.path.expanduser("~/.rclone")
    files_to_remove = [
        CONFIG_FILE,
        PID_FILE,
        os.path.join(rclone_dir, "scs.log"),
        os.path.join(rclone_dir, "scs_stop_flag"),
        os.path.join(rclone_dir, "scs_manager.log"),
        os.path.join(rclone_dir, "scs_manager.error.log")
    ]
    
    # Remove specific files
    for file in files_to_remove:
        try:
            if os.path.exists(file):
                os.remove(file)
                print(f"✅ Removed {os.path.basename(file)}")
            else:
                print(f"ℹ️ {os.path.basename(file)} not found")
        except Exception as e:
            print(f"ℹ️ Error removing {os.path.basename(file)}: {e}")
    
    # Remove all scs_ log files from .rclone folder
    try:
        for file in os.listdir(rclone_dir):
            if file.startswith("scs_") and file.endswith(".log"):
                file_path = os.path.join(rclone_dir, file)
                try:
                    os.remove(file_path)
                    print(f"✅ Removed log file: {file}")
                except Exception as e:
                    print(f"ℹ️ Error removing log file {file}: {e}")
    except Exception as e:
        print(f"ℹ️ Error accessing .rclone directory: {e}")
    
    print("\n✅ Cleanup completed!")
    print("You can now run 'scs setup' again to reconfigure the tool.")

def pause_sync(name):
    """Pause a sync configuration."""
    config = load_config()
    
    if name not in config["syncs"]:
        logger.error(f"Sync configuration '{name}' does not exist")
        sys.exit(1)
    
    if config["syncs"][name]["status"] == "paused":
        logger.info(f"Sync configuration '{name}' is already paused")
        return
    
    # Update status first
    config["syncs"][name]["status"] = "paused"
    save_config(config)
    
    # Then tell the service to reload config
    if is_service_running():
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGHUP)
            logger.info(f"Paused sync configuration '{name}'")
        except Exception as e:
            logger.error(f"Error pausing sync: {e}")
            sys.exit(1)
    else:
        logger.info(f"Sync service is not running, but marked '{name}' as paused")

def resume_sync(name):
    """Resume a paused sync configuration."""
    config = load_config()
    
    if name not in config["syncs"]:
        logger.error(f"Sync configuration '{name}' does not exist")
        sys.exit(1)
    
    if config["syncs"][name]["status"] == "active":
        logger.info(f"Sync configuration '{name}' is already active")
        return
    
    # Update status first
    config["syncs"][name]["status"] = "active"
    save_config(config)
    
    # Then tell the service to reload config
    if not is_service_running():
        logger.info("Starting sync service...")
        start_service()
        # Give the service a moment to start
        time.sleep(2)
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        logger.info(f"Resumed sync configuration '{name}'")
    except Exception as e:
        logger.error(f"Error resuming sync: {e}")
        sys.exit(1)

def uninstall():
    """Uninstall the package and remove all configurations."""
    print("\n=== Uninstalling Secure Cloud Syncer ===")
    
    # First run the cleanup process
    cleanup_setup()
    
    # Now uninstall the package
    print("\nUninstalling Python package...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "secure-cloud-syncer"],
                      check=True)
        print("✅ Package uninstalled successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error uninstalling package: {e}")
        sys.exit(1)
    
    print("\n✅ Uninstallation completed!")
    print("All configurations and the package have been removed.")

def show_service_logs(follow=False, lines=50):
    """Show the sync service logs."""
    log_file = os.path.expanduser("~/.rclone/scs.log")
    if not os.path.exists(log_file):
        print("No log file found. The service might not have started yet.")
        return
    
    try:
        if follow:
            # Use tail -f to follow the log file
            subprocess.run(['tail', '-f', '-n', str(lines), log_file])
        else:
            # Just show the last n lines
            subprocess.run(['tail', '-n', str(lines), log_file])
    except Exception as e:
        print(f"Error showing logs: {e}")

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description='Secure Cloud Syncer CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Set up rclone with Google Drive')
    
    # Cleanup command
    subparsers.add_parser('cleanup', help='Remove all configurations and created folders from setup')
    
    # Uninstall command
    subparsers.add_parser('uninstall', help='Uninstall the package and remove all configurations')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new sync configuration')
    add_parser.add_argument('name', help='Name of the sync configuration')
    add_parser.add_argument('local_path', help='Local path to sync')
    add_parser.add_argument('--remote-dir', required=True, help='Remote directory path')
    add_parser.add_argument('--mode', choices=['bidirectional', 'upload'], 
                          default='bidirectional',
                          help='Sync mode:\n'
                               '  bidirectional: Two-way sync between local and remote (default)\n'
                               '  upload: One-way sync from local to remote only')
    add_parser.add_argument('--exclude-resource-forks', action='store_true',
                          help='Exclude macOS resource fork files (._*)')
    add_parser.add_argument('--debounce-time', type=int, default=5,
                          help='Time in seconds to wait before syncing after changes (default: 5)')
    
    # List command
    subparsers.add_parser('list', help='List all sync configurations')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a sync configuration')
    remove_parser.add_argument('name', help='Name of the sync configuration to remove')
    
    # Pause command
    pause_parser = subparsers.add_parser('pause', help='Pause a sync configuration')
    pause_parser.add_argument('name', help='Name of the sync configuration to pause')
    
    # Resume command
    resume_parser = subparsers.add_parser('resume', help='Resume a paused sync configuration')
    resume_parser.add_argument('name', help='Name of the sync configuration to resume')
    
    # Service commands
    service_parser = subparsers.add_parser('service', help='Manage the sync service')
    service_subparsers = service_parser.add_subparsers(dest='service_command', help='Service commands')
    
    # Service start command
    service_subparsers.add_parser('start', help='Start the sync service')
    
    # Service stop command
    service_subparsers.add_parser('stop', help='Stop the sync service')
    
    # Service status command
    service_subparsers.add_parser('status', help='Show the status of the sync service')
    
    # Service restart command
    service_subparsers.add_parser('restart', help='Restart the sync service')
    
    # Service logs command
    logs_parser = service_subparsers.add_parser('logs', help='Show the sync service logs')
    logs_parser.add_argument('--follow', '-f', action='store_true', help='Follow the log output')
    logs_parser.add_argument('--lines', '-n', type=int, default=50, help='Number of lines to show (default: 50)')
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    # Handle commands
    if args.command == 'setup':
        setup_rclone()
    elif args.command == 'cleanup':
        cleanup_setup()
    elif args.command == 'uninstall':
        uninstall()
    elif args.command == 'add':
        add_sync(args.name, args.local_path, args.remote_dir, args.mode, args.exclude_resource_forks, args.debounce_time)
    elif args.command == 'list':
        list_syncs()
    elif args.command == 'remove':
        remove_sync(args.name)
    elif args.command == 'pause':
        pause_sync(args.name)
    elif args.command == 'resume':
        resume_sync(args.name)
    elif args.command == 'service':
        if args.service_command is None:
            service_parser.print_help()
            sys.exit(1)
        
        if args.service_command == 'start':
            start_service()
        elif args.service_command == 'stop':
            stop_service()
        elif args.service_command == 'status':
            check_service_status()
        elif args.service_command == 'restart':
            restart_service()
        elif args.service_command == 'logs':
            show_service_logs(args.follow, args.lines)

if __name__ == "__main__":
    main() 