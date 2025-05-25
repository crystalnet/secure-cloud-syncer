#!/usr/bin/env python3
"""
Monitor module for Secure Cloud Syncer.
This module provides functionality for monitoring a directory and triggering bidirectional syncs.
"""

import os
import sys
import time
import logging
import subprocess
import re
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

def check_rclone_version():
    """
    Check if rclone version is 1.58.0 or newer (required for bisync).
    
    Returns:
        bool: True if version is sufficient, False otherwise
    """
    logger = logging.getLogger("secure_cloud_syncer.monitor")
    try:
        result = subprocess.run(
            ["rclone", "version"],
            capture_output=True,
            text=True,
            check=True
        )
        version_match = re.search(r"rclone v(\d+\.\d+\.\d+)", result.stdout)
        if version_match:
            version = version_match.group(1)
            major, minor, patch = map(int, version.split('.'))
            if major > 1 or (major == 1 and minor >= 58):
                return True
        logger.error("rclone version 1.58.0 or newer is required for bisync")
        return False
    except Exception as e:
        logger.error(f"Error checking rclone version: {e}")
        return False

def build_exclude_patterns(exclude_resource_forks=False):
    """
    Build the exclude patterns for rclone.
    
    Args:
        exclude_resource_forks (bool): Whether to exclude macOS resource fork files
        
    Returns:
        list: List of exclude patterns
    """
    patterns = [
        "--exclude", ".DS_Store",
        "--exclude", ".DS_Store/**",
        "--exclude", "**/.DS_Store",
        "--exclude", ".Trash/**",
        "--exclude", "**/.Trash/**",
        "--exclude", ".localized",
        "--exclude", "**/.localized",
        "--exclude", ".Spotlight-V100",
        "--exclude", "**/.Spotlight-V100/**",
        "--exclude", ".fseventsd",
        "--exclude", "**/.fseventsd/**",
        "--exclude", ".TemporaryItems",
        "--exclude", "**/.TemporaryItems/**",
        "--exclude", ".VolumeIcon.icns",
        "--exclude", "**/.VolumeIcon.icns",
        "--exclude", ".DocumentRevisions-V100",
        "--exclude", "**/.DocumentRevisions-V100/**",
        "--exclude", ".com.apple.timemachine.donotpresent",
        "--exclude", "**/.com.apple.timemachine.donotpresent",
        "--exclude", ".AppleDouble",
        "--exclude", "**/.AppleDouble/**",
        "--exclude", ".LSOverride",
        "--exclude", "**/.LSOverride/**",
        "--exclude", "Icon?",
        "--exclude", "**/Icon?"
    ]
    
    if exclude_resource_forks:
        patterns.extend([
            "--exclude", "._*",
            "--exclude", "**/._*"
        ])
    
    return patterns

class ChangeHandler(FileSystemEventHandler):
    """
    Handler for file system events.
    """
    def __init__(self, local_dir, remote_dir, exclude_resource_forks=False, debounce_time=5, log_file=None, direction="bidirectional"):
        """
        Initialize the change handler.
        
        Args:
            local_dir (str): Path to the local directory to monitor
            remote_dir (str): Remote directory to sync with
            exclude_resource_forks (bool): Whether to exclude macOS resource fork files
            debounce_time (int): Time in seconds to wait before syncing after changes
            log_file (str): Path to the log file
            direction (str): Sync direction - "bidirectional" or "upload"
        """
        self.local_dir = local_dir
        self.remote_dir = remote_dir
        self.exclude_resource_forks = exclude_resource_forks
        self.debounce_time = debounce_time
        self.log_file = log_file
        self.direction = direction
        self.last_sync = 0
        self.sync_pending = False
        self.sync_in_progress = False
        self.exclude_patterns = build_exclude_patterns(exclude_resource_forks)
        self.logger = logging.getLogger("secure_cloud_syncer.monitor.handler")
        self.initial_sync_done = False
        
        # Check encryption settings
        try:
            result = subprocess.run(['rclone', 'config', 'show', remote_dir.split(':')[0]], 
                                  capture_output=True, text=True, check=True)
            if 'type = crypt' in result.stdout:
                filename_enc = 'standard' if 'filename_encryption = standard' in result.stdout else 'off'
                dir_enc = 'true' if 'directory_name_encryption = true' in result.stdout else 'false'
                self.logger.info(f"Using encrypted remote with settings:")
                self.logger.info(f"- Filename encryption: {filename_enc}")
                self.logger.info(f"- Directory name encryption: {dir_enc}")
        except Exception as e:
            self.logger.warning(f"Could not verify encryption settings: {e}")
        
        # Perform initial sync
        self.logger.info("Performing initial sync...")
        self.sync_directory(initial_sync=True)
        self.initial_sync_done = True
        self.logger.info("Initial sync completed")
    
    def on_any_event(self, event):
        """
        Handle any file system event.
        
        Args:
            event: The file system event
        """
        if event.is_directory:
            return
        
        # Skip temporary files and hidden files
        if event.src_path.endswith('~') or os.path.basename(event.src_path).startswith('.'):
            return
        
        # Check if the file is in the monitored directory
        try:
            rel_path = os.path.relpath(event.src_path, self.local_dir)
            if rel_path.startswith('..'):
                return
        except ValueError:
            return
        
        current_time = time.time()
        if current_time - self.last_sync < self.debounce_time:
            self.sync_pending = True
            return
        
        self.sync_pending = False
        self.last_sync = current_time
        
        # If a sync is already in progress, mark as pending and return
        if self.sync_in_progress:
            self.sync_pending = True
            self.logger.info("Sync in progress, changes will be synced after current sync completes")
            return
        
        self.sync_directory(initial_sync=False)
    
    def sync_directory(self, initial_sync=False):
        """
        Perform a sync using rclone based on the configured direction.
        
        Args:
            initial_sync (bool): Whether this is the initial sync
        """
        if self.sync_in_progress:
            self.logger.warning("Sync already in progress, skipping")
            return
        
        self.sync_in_progress = True
        try:
            if self.direction == "bidirectional":
                # Build the rclone bisync command
                cmd = [
                    "rclone",
                    "bisync",
                    self.local_dir,
                    self.remote_dir,
                    "--verbose",
                    "--log-file", self.log_file,
                    "--transfers", "4",
                    "--checkers", "8",
                    "--contimeout", "60s",
                    "--timeout", "300s",
                    "--retries", "3",
                    "--low-level-retries", "10",
                    "--progress",
                    "--stats-one-line",
                    "--stats", "5s"
                ]
                
                # Only add --resync for initial sync
                if initial_sync:
                    cmd.insert(4, "--resync")
                    self.logger.info(f"Starting initial bidirectional sync between {self.local_dir} and {self.remote_dir}")
                else:
                    self.logger.info(f"Starting bidirectional sync between {self.local_dir} and {self.remote_dir}")
            else:  # upload
                # Build the rclone sync command for one-way upload
                cmd = [
                    "rclone",
                    "sync",
                    self.local_dir,
                    self.remote_dir,
                    "--verbose",
                    "--log-file", self.log_file,
                    "--transfers", "4",
                    "--checkers", "8",
                    "--contimeout", "60s",
                    "--timeout", "300s",
                    "--retries", "3",
                    "--low-level-retries", "10",
                    "--progress",
                    "--stats-one-line",
                    "--stats", "5s"
                ]
                self.logger.info(f"Starting one-way sync from {self.local_dir} to {self.remote_dir}")
            
            # Add exclude patterns
            cmd.extend(self.exclude_patterns)
            
            try:
                # Run the sync command
                self.logger.debug(f"Running command: {' '.join(cmd)}")
                subprocess.run(cmd, check=True)
                self.logger.info("Sync completed successfully")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Error during sync: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error during sync: {e}")
            
            # Check if we need to run another sync due to pending changes
            if self.sync_pending:
                self.logger.info("Changes occurred during sync, starting another sync")
                self.sync_pending = False
                self.sync_in_progress = False
                self.sync_directory(initial_sync=False)
            
        finally:
            self.sync_in_progress = False

def start_monitoring(local_dir, remote_dir="gdrive-crypt:", exclude_resource_forks=False, debounce_time=5, log_file=None, direction="bidirectional"):
    """
    Start monitoring a directory for changes and trigger syncs.
    
    Args:
        local_dir (str): Path to the local directory to monitor
        remote_dir (str): Remote directory to sync with
        exclude_resource_forks (bool): Whether to exclude macOS resource fork files
        debounce_time (int): Time in seconds to wait before syncing after changes
        log_file (str): Path to the log file
        direction (str): Sync direction - "bidirectional" or "upload"
        
    Returns:
        Observer: The watchdog observer instance
    """
    logger = logging.getLogger("secure_cloud_syncer.monitor")
    
    try:
        # Set up log file path
        if log_file is None:
            log_dir = os.path.expanduser("~/.rclone")
            log_file = os.path.join(log_dir, "scs_monitor_rsync.log")
        
        logger.info(f"Starting monitoring for {local_dir}")
        
        # Validate inputs before starting process
        local_path = Path(local_dir)
        if not local_path.exists():
            logger.error(f"Local directory does not exist: {local_dir}")
            raise RuntimeError(f"Local directory does not exist: {local_dir}")
        
        if not local_path.is_dir():
            logger.error(f"Local path is not a directory: {local_dir}")
            raise RuntimeError(f"Local path is not a directory: {local_dir}")
        
        if not os.access(local_dir, os.R_OK):
            logger.error(f"Local directory is not readable: {local_dir}")
            raise RuntimeError(f"Local directory is not readable: {local_dir}")
        
        if not check_rclone_version():
            logger.error("rclone version check failed")
            raise RuntimeError("rclone version check failed")
        
        logger.info(f"Using log file: {log_file}")
        
        # Create event handler
        event_handler = ChangeHandler(
            local_dir=local_dir,
            remote_dir=remote_dir,
            exclude_resource_forks=exclude_resource_forks,
            debounce_time=debounce_time,
            log_file=log_file,
            direction=direction
        )
        
        # Create and start observer
        observer = Observer()
        observer.schedule(event_handler, local_dir, recursive=True)
        observer.start()
        
        logger.info(f"Started monitoring {local_dir}")
        return observer
        
    except Exception as e:
        logger.error(f"Error starting monitor: {e}", exc_info=True)
        raise

def main():
    """
    Main entry point for the monitor script.
    """
    if len(sys.argv) < 2:
        print("Usage: python monitor.py <local_directory> [--exclude-resource-forks] [--debounce-time <seconds>]")
        sys.exit(1)
    
    local_dir = sys.argv[1]
    exclude_resource_forks = "--exclude-resource-forks" in sys.argv
    debounce_time = 5
    
    # Parse debounce time if provided
    if "--debounce-time" in sys.argv:
        try:
            debounce_index = sys.argv.index("--debounce-time")
            if debounce_index + 1 < len(sys.argv):
                debounce_time = int(sys.argv[debounce_index + 1])
        except (ValueError, IndexError):
            print("Invalid debounce time. Using default value of 5 seconds.")
    
    observer = start_monitoring(
        local_dir,
        exclude_resource_forks=exclude_resource_forks,
        debounce_time=debounce_time
    )
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        sys.exit(0)

if __name__ == "__main__":
    main() 