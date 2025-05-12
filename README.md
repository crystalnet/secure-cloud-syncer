# Secure Cloud Syncer

A secure cloud syncing tool that provides encrypted synchronization with Google Drive, featuring automatic monitoring and bidirectional sync capabilities.

## Features

- 🔒 End-to-end encryption for all synced files
- 🔄 Bidirectional synchronization with Google Drive
- 👀 Automatic monitoring of local folders
- 🚀 Background service for continuous operation
- 🔄 On-the-fly configuration updates
- 🛠️ Easy setup and configuration

## Installation

### Prerequisites

- Python 3.6 or higher
- rclone (will be installed automatically)
- Google Drive account

### Installation Options

#### 1. Direct Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/crystalnet/secure-cloud-syncer.git
cd secure-cloud-syncer

# Install the package and dependencies
pip install -e .
```

This will:
- Install the package and all dependencies
- Set up rclone configuration
- Install the background service (but not start it)

#### 2. Using pip (Coming Soon)

```bash
pip install secure-cloud-syncer
```

#### 3. Using Homebrew (Coming Soon)

```bash
brew install secure-cloud-syncer
```

## Usage

### Initial Setup

1. Configure rclone (if not done during installation):
   ```bash
   scs setup
   ```

2. Add a folder to sync:
   ```bash
   scs add <name> <local_path>
   ```
   Example:
   ```bash
   scs add documents ~/Documents
   ```

3. Start the sync service:
   ```bash
   scs service start
   ```

### Managing Syncs

- List all sync configurations:
  ```bash
  scs list
  ```

- Start a specific sync:
  ```bash
  scs start <name>
  ```

- Stop a specific sync:
  ```bash
  scs stop <name>
  ```

- Restart a specific sync:
  ```bash
  scs restart <name>
  ```

### Service Management

- Start the sync service:
  ```bash
  scs service start
  ```

- Stop the sync service:
  ```bash
  scs service stop
  ```

- Check service status:
  ```bash
  scs service status
  ```

- Reload service configuration:
  ```bash
  scs service reload
  ```

## Configuration

The tool uses rclone for cloud synchronization. Configuration files are stored in:
- `~/.rclone/rclone.conf` - rclone configuration
- `~/.rclone/scs_config.json` - sync configurations

## Logs

Logs are stored in:
- `~/.rclone/scs.log` - CLI and sync operations
- `~/Library/Logs/secure_cloud_syncer/` - Service logs

## Development

### Project Structure

```
secure-cloud-syncer/
├── setup.py               # Package setup file
├── README.md
├── LICENSE
├── requirements.txt
└── secure_cloud_syncer/
    ├── __init__.py
    ├── cli.py             # Command-line interface
    ├── config.py          # Configuration management
    ├── manager.py         # Sync manager daemon
    ├── monitor.py         # File system monitoring
    ├── sync.py            # Sync operations
    ├── scripts/
    │   ├── rclone_setup.sh
    │   └── service_setup.sh
    └── templates/
        └── .rclone.conf.template
```

### Running Tests

```bash
python -m pytest tests/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request 