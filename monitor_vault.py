#!/usr/bin/env python3
"""
DEPRECATED: This script is deprecated and will be removed in a future version.
Please use the secure_cloud_syncer package instead:
    python3 -m secure_cloud_syncer.sync.monitor <vault_dir> <remote_dir> <exclude_patterns> <debounce_time> <log_file>
    
The new implementation provides improved features:
- Queue-based sync management to handle multiple overlapping syncs
- Thread-safe implementation
- Better error handling and logging
- More robust debouncing
"""

import time
import os
import sys
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, vault_dir, remote_dir, exclude_patterns, debounce_time, log_file):
        self.vault_dir = vault_dir
        self.remote_dir = remote_dir
        self.exclude_patterns = exclude_patterns
        self.debounce_time = debounce_time
        self.log_file = log_file
        self.last_sync = 0
        self.sync_in_progress = False

    def on_any_event(self, event):
        if event.is_directory:
            return
        
        # Ignore temporary files
        if event.src_path.endswith('.tmp') or event.src_path.endswith('.temp'):
            return
            
        current_time = time.time()
        
        # Debounce: only sync if enough time has passed since the last sync
        if current_time - self.last_sync < self.debounce_time:
            return
            
        # Don't start a new sync if one is already in progress
        if self.sync_in_progress:
            return
            
        self.sync_in_progress = True
        self.last_sync = current_time
        
        # Log the change
        with open(self.log_file, 'a') as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Change detected: {event.src_path}\n")
        
        print(f"Change detected: {event.src_path}")
        print("Starting bidirectional sync...")
        
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
            subprocess.run(cmd, check=True)
            print("Sync completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"Error during sync: {e}")
            with open(self.log_file, 'a') as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Error during sync: {e}\n")
        finally:
            self.sync_in_progress = False

def main():
    if len(sys.argv) < 6:
        print("Usage: python monitor_vault.py <vault_dir> <remote_dir> <exclude_patterns> <debounce_time> <log_file>")
        sys.exit(1)
        
    vault_dir = sys.argv[1]
    remote_dir = sys.argv[2]
    exclude_patterns = sys.argv[3]
    debounce_time = float(sys.argv[4])
    log_file = sys.argv[5]
    
    event_handler = ChangeHandler(vault_dir, remote_dir, exclude_patterns, debounce_time, log_file)
    observer = Observer()
    observer.schedule(event_handler, vault_dir, recursive=True)
    observer.start()
    
    print(f"Monitoring {vault_dir} for changes...")
    print(f"Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nMonitoring stopped")
    
    observer.join()

if __name__ == "__main__":
    main() 