# Secure Cloud Syncer

A secure file synchronization tool that encrypts files before uploading them to Google Drive while preserving the original file structure and names. This tool provides both one-way and bidirectional synchronization options.

## Features

- 🔒 **Secure Encryption**: Files are encrypted before being uploaded to Google Drive
- 📁 **Structure Preservation**: Maintains original file structure and names
- 🔄 **Sync Options**: 
  - One-way sync (local to cloud)
  - Bidirectional sync (one-time two-way synchronization)
- 🚫 **System File Exclusion**: Automatically excludes system files (e.g., .DS_Store)
- 📊 **Progress Tracking**: Real-time progress information during sync
- 🔧 **Cross-Platform**: Supports macOS, Linux, and Windows
- ⚡ **Performance**: Optimized transfer settings for better sync speed

## Prerequisites

- Python 3.x
- rclone
- rclonesync (for bidirectional sync)
- Google Drive account

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
   - Install required dependencies based on your OS
   - Make all scripts executable
   - Create necessary directories

3. Configure rclone with your Google Drive:
   ```bash
   ./setup_rclone.sh
   ```
   Follow the prompts to:
   - Set up Google Drive access
   - Configure encryption settings
   - Create the encrypted remote

## Usage

### One-Way Sync (Local to Cloud)

To sync a local directory to Google Drive:
```bash
./sync.sh /path/to/your/folder
```

Options:
- `--exclude-resource-forks`: Exclude macOS resource fork files (._*)

### Bidirectional Sync

To perform a one-time bidirectional sync between your local directory and Google Drive:
```bash
./bidirectional_sync.sh /path/to/your/folder
```

Options:
- `--exclude-resource-forks`: Exclude macOS resource fork files (._*)

## File Exclusions

The following files are automatically excluded from sync:
- `.DS_Store` files and directories
- `.Trash` directories
- `.localized` files
- `.Spotlight-V100` directories
- `.fseventsd` directories
- `.TemporaryItems` directories
- `.VolumeIcon.icns` files
- `.DocumentRevisions-V100` directories
- `.com.apple.timemachine.donotpresent` files
- `.AppleDouble` directories
- `.LSOverride` directories
- `Icon?` files
- Resource fork files (._*) - optional

## Configuration

### rclone Configuration

The rclone configuration is stored in `~/.rclone/rclone.conf`. A template is provided in `.rclone.conf.template`. The configuration includes:
- Google Drive remote setup
- Encryption settings
- Transfer optimizations

### Log Files

- One-way sync logs: `~/.rclone/sync.log`
- Bidirectional sync logs: `~/.rclone/bidirectional_sync.log`

## Security

- Files are encrypted using rclone's encryption feature
- File names and structure remain unencrypted for easy navigation
- Encryption password is stored securely and never committed to version control
- System files are automatically excluded from sync

## Troubleshooting

1. If sync seems stuck:
   - Check the log files in `~/.rclone/`
   - Ensure you have proper permissions for the local directory
   - Verify your internet connection

2. If files aren't syncing:
   - Check if the files are in the excluded patterns
   - Verify rclone configuration is correct
   - Ensure Google Drive access is properly configured

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details. 