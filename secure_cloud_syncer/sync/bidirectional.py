#!/usr/bin/env python3
"""
Bidirectional sync module for Secure Cloud Syncer.
This module provides functionality for syncing files between a local directory and Google Drive in both directions.
"""

import os
import sys
import logging
import subprocess
import re
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

def check_rclone_version():
    """
    Check if rclone version is 1.58.0 or newer for bisync support.
    
    Returns:
        bool: True if rclone version is 1.58.0 or newer, False otherwise
    """
    try:
        result = subprocess.run(["rclone", "version"], capture_output=True, text=True, check=True)
        version_match = re.search(r'rclone v(\d+\.\d+\.\d+)', result.stdout)
        if version_match:
            version = version_match.group(1)
            major, minor, patch = map(int, version.split('.'))
            if major > 1 or (major == 1 and minor > 57):
                return True
            logger.error(f"rclone version {version} is older than 1.58.0 which is required for bisync")
            return False
        logger.error("Could not determine rclone version")
        return False
    except subprocess.CalledProcessError:
        logger.error("Failed to run rclone version command")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking rclone version: {e}")
        return False

def build_exclude_patterns(exclude_resource_forks=False):
    """
    Build the exclude patterns for rclone.
    
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
    
    return exclude_patterns

def sync_bidirectional(local_dir, remote_dir="gdrive-crypt:", exclude_resource_forks=False, log_file=None):
    """
    Perform a bidirectional sync between a local directory and Google Drive using rclone bisync.
    
    Args:
        local_dir (str): Path to the local directory to sync
        remote_dir (str): Remote directory to sync with
        exclude_resource_forks (bool): Whether to exclude macOS resource fork files
        log_file (str): Path to the log file
        
    Returns:
        bool: True if sync was successful, False otherwise
    """
    # Check rclone version
    if not check_rclone_version():
        logger.error("rclone version 1.58.0 or newer is required for bisync")
        return False
    
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
    
    # Build the rclone bisync command
    cmd = [
        "rclone",
        "bisync",
        local_dir,
        remote_dir,
        "--resync",
        "--verbose",
        "--log-file", log_file
    ]
    
    # Add exclude patterns
    cmd.extend(exclude_patterns)
    
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