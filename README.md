# Secure Cloud Syncer

A secure and efficient tool for synchronizing files between your local machine and Google Drive using rclone, while maintaining your file structure and ensuring data security.

## Overview

This project provides a secure way to sync your files with Google Drive using rclone, a powerful command-line tool for syncing files and directories to and from various cloud storage providers. It ensures:

- Secure file transfer with encryption
- Preservation of file structure
- Efficient synchronization
- Reliable backup solution

## Prerequisites

- [rclone](https://rclone.org/downloads/) installed on your system
- Google Drive account
- Python 3.x (for automation scripts)

## Setup

1. Install rclone:
   ```bash
   # macOS (using Homebrew)
   brew install rclone

   # Linux
   sudo apt-get install rclone

   # Windows
   # Download from https://rclone.org/downloads/
   ```

2. Configure rclone for Google Drive:
   ```bash
   rclone config
   ```
   Follow the interactive prompts to:
   - Select "New remote"
   - Choose "Google Drive" as the storage type
   - Follow the authentication process
   - Name your remote (e.g., "gdrive")

## Usage

1. Basic sync command:
   ```bash
   rclone sync /path/to/local/folder gdrive:remote/folder
   ```

2. Sync with encryption:
   ```bash
   rclone sync --crypt-remote gdrive:remote/folder /path/to/local/folder
   ```

## Features

- **Secure Transfer**: All data is transferred over encrypted connections
- **File Structure Preservation**: Maintains your local directory structure in the cloud
- **Efficient Syncing**: Only transfers changed files
- **Conflict Resolution**: Handles file conflicts intelligently
- **Bandwidth Control**: Option to limit bandwidth usage
- **Scheduled Sync**: Can be automated using cron jobs or system schedulers

## Security Considerations

- All transfers are encrypted in transit
- Optional client-side encryption for sensitive data
- Secure authentication using OAuth2
- No storage of sensitive credentials in plain text

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [rclone](https://rclone.org/) - The underlying sync engine
- Google Drive API 