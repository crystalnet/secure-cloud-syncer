#!/usr/bin/env python3

"""
Rclone configuration script.
This script sets up rclone with Google Drive authentication and encryption.
"""

import os
import sys
import subprocess
from pathlib import Path

def configure_rclone():
    """Configure rclone with Google Drive."""
    print("=== Configuring rclone ===")
    print("Please follow the prompts to set up your Google Drive remote")
    print("When asked for the remote name, use 'gdrive'")
    print("When asked for the storage type, choose 'drive'")
    print("When asked for client_id and client_secret, press Enter to use defaults")
    print("When asked for scope, choose 'drive.file'")
    print("When asked for root_folder_id, press Enter")
    print("When asked for service_account_file, press Enter")
    print("When asked for advanced config, choose 'n'")
    print("When asked for auto config, choose 'y'")
    print("When asked for team drive, choose 'n'")
    
    # Use Python's rclone package to configure
    try:
        import rclone
        rclone.config()
    except ImportError:
        print("Error: rclone Python package not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error configuring rclone: {e}")
        sys.exit(1)

if __name__ == "__main__":
    configure_rclone() 