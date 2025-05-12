#!/usr/bin/env python3
"""
Setup script for Secure Cloud Syncer.
This script handles the installation of the package and its dependencies,
as well as setting up the service and rclone configuration.
"""

import os
import sys
import subprocess
from setuptools import setup, find_packages

def install_service():
    """Install the sync service."""
    script_path = os.path.join(os.path.dirname(__file__), 'secure_cloud_syncer', 'scripts', 'service_setup.sh')
    if os.path.exists(script_path):
        os.chmod(script_path, 0o755)
        subprocess.run([script_path, 'install'], check=True)
    else:
        print("Warning: Service setup script not found at", script_path)

def setup_rclone():
    """Set up rclone configuration."""
    script_path = os.path.join(os.path.dirname(__file__), 'secure_cloud_syncer', 'scripts', 'rclone_setup.sh')
    if os.path.exists(script_path):
        os.chmod(script_path, 0o755)
        subprocess.run([script_path], check=True)
    else:
        print("Warning: Rclone setup script not found at", script_path)

setup(
    name="secure_cloud_syncer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "watchdog>=2.1.0",
        "psutil>=5.9.0",
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

# Run post-installation steps
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        install_service()
        setup_rclone() 