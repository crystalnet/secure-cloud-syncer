#!/usr/bin/env python3
"""
File system monitoring module for Secure Cloud Syncer.
This module monitors a directory for changes and triggers a bidirectional sync when changes are detected.
"""

import time
import os
import sys
import logging
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser("~/.rclone/monitor_sync.log"))
    ]
)
logger = logging.getLogger("secure_cloud_syncer.monitor")

class ChangeHandler(FileSystemEventHandler):
    """
    Handler for file system events that triggers bidirectional sync when changes are detected.
    """
    
    def __init__(self, vault_dir, remote_dir, exclude_patterns, debounce_time, log_file):
        """
        Initialize the change handler.
        
        Args:
            vault_dir (str): Path to the vault directory to monitor
            remote_dir (str): Remote directory to sync with
            exclude_patterns (str): Rclone exclude patterns
            debounce_time (float): Time in seconds to wait after a change before triggering sync
            log_file (str): Path to the log file
        """
        self.vault_dir = vault_dir
        self.remote_dir = remote_dir
        self.exclude_patterns = exclude_patterns
        self.debounce_time = debounce_time
        self.log_file = log_file
        self.last_sync = 0
        self.sync_in_progress = False
        logger.info(f"Initialized change handler for {vault_dir}")

    def on_any_event(self, event):
        """
        Handle any file system event.
        
        Args:
            event: The file system event
        """
        if event.is_directory:
            return
        
        # Ignore temporary files
        if event.src_path.endswith('.tmp') or event.src_path.endswith('.temp'):
            return
            
        current_time = time.time()
        
        # Debounce: only sync if enough time has passed since the last sync
        if current_time - self.last_sync < self.debounce_time:
            logger.debug(f"Ignoring change due to debounce: {event.src_path}")
            return
            
        # Don't start a new sync if one is already in progress
        if self.sync_in_progress:
            logger.debug(f"Ignoring change due to sync in progress: {event.src_path}")
            return
            
        self.sync_in_progress = True
        self.last_sync = current_time
        
        # Log the change
        logger.info(f"Change detected: {event.src_path}")
        logger.info("Starting bidirectional sync...")
        
        # Build the rclonesync command
        cmd = [
            "rclonesync",
            self.vault_dir,
            self.remote_dir,
            "--rclone-args", self.exclude_patterns + " --verbose --log-file " + self.log_file,
            "--rclone-timeout", "300",
            "--rclone-retries", "3",
            "--rclone-low-level-retries", "10",
            "--rclone-transfers", "4",
            "--rclone-checkers", "8",
            "--rclone-contimeout", "60s",
            "--rclone-timeout", "300s",
            "--rclone-retries", "3",
            "--rclone-low-level-retries", "10",
            "--rclone-progress",
            "--rclone-stats-one-line",
            "--rclone-stats", "5s",
            "--log-level", "INFO",
            "--log-file", self.log_file,
            "--one-time"
        ]
        
        try:
            # Run the sync command
            logger.debug(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            logger.info("Sync completed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error during sync: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during sync: {e}")
        finally:
            self.sync_in_progress = False

def start_monitoring(vault_dir, remote_dir, exclude_patterns, debounce_time, log_file):
    """
    Start monitoring a directory for changes.
    
    Args:
        vault_dir (str): Path to the vault directory to monitor
        remote_dir (str): Remote directory to sync with
        exclude_patterns (str): Rclone exclude patterns
        debounce_time (float): Time in seconds to wait after a change before triggering sync
        log_file (str): Path to the log file
    """
    # Validate inputs
    vault_path = Path(vault_dir)
    if not vault_path.exists():
        logger.error(f"Vault directory does not exist: {vault_dir}")
        return False
    
    if not vault_path.is_dir():
        logger.error(f"Vault path is not a directory: {vault_dir}")
        return False
    
    if not os.access(vault_dir, os.R_OK):
        logger.error(f"Vault directory is not readable: {vault_dir}")
        return False
    
    # Create log directory if it doesn't exist
    log_path = Path(log_file).parent
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Set up the event handler and observer
    event_handler = ChangeHandler(vault_dir, remote_dir, exclude_patterns, debounce_time, log_file)
    observer = Observer()
    observer.schedule(event_handler, vault_dir, recursive=True)
    
    # Start the observer
    observer.start()
    logger.info(f"Started monitoring {vault_dir}")
    logger.info(f"Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Monitoring stopped")
    
    observer.join()
    return True

def main():
    """
    Main entry point for the monitor script.
    """
    if len(sys.argv) < 6:
        print("Usage: python monitor_vault.py <vault_dir> <remote_dir> <exclude_patterns> <debounce_time> <log_file>")
        sys.exit(1)
        
    vault_dir = sys.argv[1]
    remote_dir = sys.argv[2]
    exclude_patterns = sys.argv[3]
    debounce_time = float(sys.argv[4])
    log_file = sys.argv[5]
    
    success = start_monitoring(vault_dir, remote_dir, exclude_patterns, debounce_time, log_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 