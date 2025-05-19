# Secure Cloud Syncer

A secure cloud synchronization tool that provides encrypted, bidirectional syncing with Google Drive.

## Features

- Encrypted file synchronization with Google Drive
- Bidirectional sync support
- Real-time file monitoring
- Resource fork handling for macOS
- Service-based background operation
- Simple command-line interface
- Flexible Google Drive access levels (full or restricted)

## Installation

### Prerequisites

- Python 3.6 or higher
- rclone binary (required for Google Drive configuration)

Install rclone:
- macOS: `brew install rclone`
- Linux: `curl https://rclone.org/install.sh | sudo bash`
- Windows: Download from [rclone.org/downloads](https://rclone.org/downloads/)

### From Source

1. Clone the repository:
   ```bash
   git clone https://github.com/crystalnet/secure-cloud-syncer.git
   cd secure-cloud-syncer
   ```

2. Install the package:
   ```bash
   pip3 install .
   ```

This will:
- Install the package and all dependencies
- Set up the sync service
- Create the `scs` command-line tool

Note: After installation, you may need to restart your terminal or run `source ~/.zshrc` (or your shell's rc file) to update your PATH.

### From PyPI (Coming Soon)

```bash
pip3 install secure-cloud-syncer
```

### From Homebrew (Coming Soon)

```bash
brew install secure-cloud-syncer
```

### From Chocolatey (Coming Soon)

```bash
choco install secure-cloud-syncer
```

## Usage

1. Set up rclone with Google Drive:
   ```bash
   scs setup
   ```
   During setup, you'll be asked to choose between two Google Drive access levels:
   - Full Access (recommended): Can sync any folder in your Google Drive
   - Restricted Access: Can only sync folders created by the tool

2. Add a folder to sync:
   ```bash
   scs add my-sync ~/Documents/my-folder --remote-dir "My Folder" --mode bidirectional
   ```

3. Start the sync service:
   ```bash
   scs service start
   ```

4. Check sync status:
   ```bash
   scs list
   ```

## Configuration

The sync service automatically monitors the configuration file at `~/.rclone/scs_config.json`. You can modify this file directly or use the CLI commands to manage sync configurations.

### Google Drive Access Levels

When setting up Google Drive, you can choose between two access levels:

1. **Full Access** (`drive` scope)
   - Can sync any folder in your Google Drive
   - No need to share folders with rclone
   - Less private but more convenient
   - Recommended for most users

2. **Restricted Access** (`drive.file` scope)
   - Can only sync folders created by the tool
   - More private but less convenient
   - Cannot sync existing folders unless created by the tool
   - Recommended for privacy-conscious users

## Logs

Logs are stored in `~/.rclone/scs.log`. You can monitor the sync service's operation by checking this file.

## Development

For development, install the package in editable mode:
```bash
pip3 install -e .
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 