#!/usr/bin/env python3
"""
Bidirectional sync module for Secure Cloud Syncer.
This module provides functionality for syncing files between a local directory and Google Drive in both directions.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser("~/.rclone/bidirectional_sync.log"))
    ]
)
logger = logging.getLogger("secure_cloud_syncer.bidirectional")

def build_exclude_patterns(exclude_resource_forks=False):
    """
    Build the exclude patterns for rclonesync.
    
    Args:
        exclude_resource_forks (bool): Whether to exclude macOS resource fork files
        
    Returns:
        str: The exclude patterns as a string
    """
    exclude_patterns = [
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
        exclude_patterns.extend([
            "--exclude", "._*",
            "--exclude", "**/._*"
        ])
        logger.info("Excluding macOS resource fork files (._*)")
    
    return " ".join(exclude_patterns)

def sync_bidirectional(local_dir, remote_dir="gdrive_encrypted:", exclude_resource_forks=False, log_file=None):
    """
    Perform a bidirectional sync between a local directory and Google Drive.
    
    Args:
        local_dir (str): Path to the local directory to sync
        remote_dir (str): Remote directory to sync with
        exclude_resource_forks (bool): Whether to exclude macOS resource fork files
        log_file (str): Path to the log file
        
    Returns:
        bool: True if sync was successful, False otherwise
    """
    # Validate inputs
    local_path = Path(local_dir)
    if not local_path.exists():
        logger.error(f"Local directory does not exist: {local_dir}")
        return False
    
    if not local_path.is_dir():
        logger.error(f"Local path is not a directory: {local_dir}")
        return False
    
    if not os.access(local_dir, os.R_OK):
        logger.error(f"Local directory is not readable: {local_dir}")
        return False
    
    # Set default log file if not provided
    if log_file is None:
        log_file = os.path.expanduser("~/.rclone/bidirectional_sync.log")
    
    # Create log directory if it doesn't exist
    log_path = Path(log_file).parent
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Build the exclude patterns
    exclude_patterns = build_exclude_patterns(exclude_resource_forks)
    
    # Build the rclonesync command
    cmd = [
        "rclonesync",
        local_dir,
        remote_dir,
        "--rclone-args", exclude_patterns + " --verbose --log-file " + log_file,
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
        "--log-file", log_file,
        "--one-time"
    ]
    
    # Log the start of the sync
    logger.info(f"Starting bidirectional sync between {local_dir} and {remote_dir}")
    
    try:
        # Run the sync command
        logger.debug(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        logger.info("Bidirectional sync completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during bidirectional sync: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during bidirectional sync: {e}")
        return False

def main():
    """
    Main entry point for the bidirectional sync script.
    """
    if len(sys.argv) < 2:
        print("Usage: python bidirectional.py <local_directory> [--exclude-resource-forks]")
        sys.exit(1)
    
    local_dir = sys.argv[1]
    exclude_resource_forks = "--exclude-resource-forks" in sys.argv
    
    success = sync_bidirectional(local_dir, exclude_resource_forks=exclude_resource_forks)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 