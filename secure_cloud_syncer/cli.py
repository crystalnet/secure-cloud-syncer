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
    """Set up rclone with Google Drive authentication and encryption."""
    setup_script = Path(__file__).parent.parent / "setup.sh"
    
    if not setup_script.exists():
        logger.error("Setup script not found")
        sys.exit(1)
    
    try:
        # Make the script executable
        setup_script.chmod(0o755)
        # Run the setup script
        subprocess.run([str(setup_script)], check=True)
        logger.info("Rclone setup completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to setup rclone: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during rclone setup: {e}")
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Secure Cloud Syncer CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Setup command
    subparsers.add_parser("setup", help="Set up rclone with Google Drive authentication and encryption")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new sync configuration")
    add_parser.add_argument("name", help="Name of the sync configuration")
    add_parser.add_argument("local_dir", help="Local directory to sync")
    add_parser.add_argument("--remote-dir", required=True, help="Remote directory to sync")
    add_parser.add_argument("--mode", choices=["one-way", "bidirectional", "monitor"],
                          default="one-way", help="Sync mode")
    add_parser.add_argument("--exclude-resource-forks", action="store_true",
                          help="Exclude macOS resource fork files")
    add_parser.add_argument("--debounce-time", type=int, default=5,
                          help="Debounce time for monitor mode (in seconds)")
    
    # List command
    subparsers.add_parser("list", help="List all sync configurations")
    
    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a sync configuration")
    remove_parser.add_argument("name", help="Name of the sync configuration to remove")
    
    # Service commands
    service_parser = subparsers.add_parser("service", help="Manage the sync service")
    service_subparsers = service_parser.add_subparsers(dest="service_command",
                                                     help="Service command to execute")
    
    service_subparsers.add_parser("start", help="Start the sync service")
    service_subparsers.add_parser("stop", help="Stop the sync service")
    service_subparsers.add_parser("reload", help="Reload the sync service configuration")
    service_subparsers.add_parser("status", help="Check the sync service status")
    
    args = parser.parse_args()
    
    if args.command == "setup":
        setup_rclone()
    elif args.command == "add":
        add_sync(args.name, args.local_dir, args.remote_dir, args.mode,
                args.exclude_resource_forks, args.debounce_time)
    elif args.command == "list":
        list_syncs()
    elif args.command == "remove":
        remove_sync(args.name)
    elif args.command == "service":
        if args.service_command == "start":
            start_service()
        elif args.service_command == "stop":
            stop_service()
        elif args.service_command == "reload":
            reload_service()
        elif args.service_command == "status":
            if is_service_running():
                print("Sync service is running")
            else:
                print("Sync service is not running")
        else:
            parser.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 