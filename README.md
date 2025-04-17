# Secure Cloud Syncer

A tool for securely syncing files with Google Drive using encryption.

## Features

- **One-way Sync**: Sync files from a local directory to an encrypted Google Drive folder
- **Bidirectional Sync**: Sync files between a local directory and an encrypted Google Drive folder using rclone's bisync feature
- **File Monitoring**: Monitor a directory for changes and automatically trigger syncs
- **Cross-Platform**: Works on macOS, Linux, and Windows
- **Encryption**: All files are encrypted before being uploaded to Google Drive
- **System File Exclusion**: Automatically excludes system files like `.DS_Store`

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/secure-cloud-syncer.git
   cd secure-cloud-syncer
   ```

2. Run the setup script:
   ```bash
   ./setup.sh
   ```

   This will:
   - Install required dependencies (rclone, Python packages)
   - Set up rclone with Google Drive
   - Configure encryption

## Requirements

- rclone 1.58.0 or newer (for bisync support)
- Python 3.6+
- watchdog (for file monitoring)

## Usage

### One-way Sync

To sync files from a local directory to Google Drive:

```bash
./sync.sh [--exclude-resource-forks] <local_directory>
```

Example:
```bash
./sync.sh ~/Documents
```

### Bidirectional Sync

To sync files between a local directory and Google Drive in both directions:

```bash
./bidirectional_sync.sh [--exclude-resource-forks] <local_directory>
```

Example:
```bash
./bidirectional_sync.sh ~/secure_vault
```

### File Monitoring

To monitor a directory for changes and automatically trigger bidirectional syncs:

```bash
./monitor.sh [--exclude-resource-forks] [--debounce SECONDS] <vault_directory>
```

Example:
```bash
./monitor.sh ~/secure_vault
```

Example with options:
```bash
./monitor.sh --exclude-resource-forks --debounce 10 ~/secure_vault
```

## Python Package

The project also provides a Python package for more advanced usage:

```python
from secure_cloud_syncer.sync import one_way, bidirectional, monitor

# One-way sync
one_way.sync_directory("/path/to/local/dir")

# Bidirectional sync
bidirectional.sync_bidirectional("/path/to/local/dir")

# Start monitoring
monitor.start_monitoring("/path/to/vault/dir", "gdrive_encrypted:", exclude_patterns, 5.0, "/path/to/log/file")
```

## Options

- `--exclude-resource-forks`: Exclude macOS resource fork files (._*)
- `--debounce SECONDS`: Set the debounce time in seconds (default: 5)

## Logs

Logs are stored in:
- `~/.rclone/sync.log` for one-way syncs
- `~/.rclone/bidirectional_sync.log` for bidirectional syncs
- `~/.rclone/monitor_sync.log` for monitoring

## License

MIT 