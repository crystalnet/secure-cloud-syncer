#!/usr/bin/env python3
"""
Setup script for Secure Cloud Syncer.
This script handles the installation of the package and its dependencies.
"""

import os
import sys
import subprocess
from setuptools import setup, find_packages
from pathlib import Path

def check_rclone():
    """Check if rclone binary is installed."""
    try:
        subprocess.run(['rclone', 'version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def install_service():
    """Install the sync service."""
    service_script = Path(__file__).parent / "secure_cloud_syncer" / "scripts" / "service_setup.sh"
    if service_script.exists():
        subprocess.run(['bash', str(service_script)], check=True)

setup(
    name="secure-cloud-syncer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "watchdog>=2.1.0",
        "psutil>=5.9.0",
        "rclone>=0.1.0",  # Python wrapper for rclone
    ],
    entry_points={
        "console_scripts": [
            "scs=secure_cloud_syncer.cli:main",
        ],
    },
    package_data={
        "secure_cloud_syncer": [
            "scripts/*.sh",
            "templates/*",
        ],
    },
    python_requires=">=3.6",
    author="Konstantin Schmidt",
    author_email="konsti7@gmx.net",
    description="A secure cloud syncing tool with encryption and monitoring",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/crystalnet/secure-cloud-syncer",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)

# Check for rclone binary
if __name__ == "__main__":
    if not check_rclone():
        print("\nError: rclone binary not found!")
        print("Please install rclone first:")
        print("  macOS: brew install rclone")
        print("  Linux: curl https://rclone.org/install.sh | sudo bash")
        print("  Windows: Download from https://rclone.org/downloads/")
        sys.exit(1)
    
    install_service() 