# CV Lab Backup Scripts

This directory contains scripts for automating CV Lab backups.

## backup-cvlab.sh

Automated backup script that creates a backup via the API and optionally downloads it to a specified location.

### Prerequisites

- `curl` - For making API requests
- `jq` - For parsing JSON responses

Install on macOS:
```bash
brew install jq
```

Install on Ubuntu/Debian:
```bash
sudo apt-get install jq
```

### Usage

Basic usage (creates backup on server):
```bash
./scripts/backup-cvlab.sh
```

Download backup to external directory:
```bash
./scripts/backup-cvlab.sh --dest /path/to/backups
```

Include exported files:
```bash
./scripts/backup-cvlab.sh --dest /path/to/backups --exports
```

Keep only last 5 backups:
```bash
./scripts/backup-cvlab.sh --dest /path/to/backups --keep 5
```

Use custom API host:
```bash
./scripts/backup-cvlab.sh --host myserver.com:8000 --dest /backups
```

### Options

- `-h, --host HOST` - API host (default: localhost:8000)
- `-d, --dest DIR` - Destination directory for backups
- `-e, --exports` - Include exported files in backup
- `-k, --keep N` - Keep only the last N backups (default: 7)
- `-v, --verbose` - Verbose output
- `--help` - Show help message

### Examples

#### Daily Backup to External Drive

```bash
#!/bin/bash
# daily-backup.sh

./scripts/backup-cvlab.sh \
  --dest /Volumes/Backup/cvlab \
  --keep 30 \
  --verbose
```

#### Weekly Full Backup with Exports

```bash
#!/bin/bash
# weekly-backup.sh

./scripts/backup-cvlab.sh \
  --dest /backups/cvlab/weekly \
  --exports \
  --keep 4 \
  --verbose
```

### Automated Backups with Cron

Add to your crontab (`crontab -e`):

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/cvlab/scripts/backup-cvlab.sh --dest /backups/cvlab --keep 7

# Weekly backup with exports on Sunday at 3 AM
0 3 * * 0 /path/to/cvlab/scripts/backup-cvlab.sh --dest /backups/cvlab/weekly --exports --keep 4

# Monthly backup on the 1st at 4 AM
0 4 1 * * /path/to/cvlab/scripts/backup-cvlab.sh --dest /backups/cvlab/monthly --exports --keep 12
```

### Automated Backups with systemd (Linux)

Create a systemd service and timer:

**Service file** (`/etc/systemd/system/cvlab-backup.service`):
```ini
[Unit]
Description=CV Lab Backup Service
After=network.target

[Service]
Type=oneshot
User=your-username
ExecStart=/path/to/cvlab/scripts/backup-cvlab.sh --dest /backups/cvlab --keep 7
StandardOutput=journal
StandardError=journal
```

**Timer file** (`/etc/systemd/system/cvlab-backup.timer`):
```ini
[Unit]
Description=CV Lab Daily Backup Timer
Requires=cvlab-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable cvlab-backup.timer
sudo systemctl start cvlab-backup.timer
sudo systemctl status cvlab-backup.timer
```

### Docker Integration

If running CV Lab in Docker, you can mount a backup directory:

```bash
docker run -d \
  -v cvlab_data:/app/data \
  -v /path/to/backups:/backups \
  -p 8000:8000 \
  cvlab
```

Then run the backup script:
```bash
docker exec cvlab /app/scripts/backup-cvlab.sh --dest /backups
```

Or from the host:
```bash
./scripts/backup-cvlab.sh --host localhost:8000 --dest /path/to/backups
```

### Backup to Cloud Storage

#### AWS S3

```bash
#!/bin/bash
# backup-to-s3.sh

BACKUP_DIR="/tmp/cvlab-backups"
S3_BUCKET="s3://my-bucket/cvlab-backups"

# Create backup
./scripts/backup-cvlab.sh --dest "$BACKUP_DIR" --exports

# Upload to S3
aws s3 sync "$BACKUP_DIR" "$S3_BUCKET" --delete

# Clean up local backups older than 7 days
find "$BACKUP_DIR" -name "cvlab_backup_*.zip" -mtime +7 -delete
```

#### Google Drive (using rclone)

```bash
#!/bin/bash
# backup-to-gdrive.sh

BACKUP_DIR="/tmp/cvlab-backups"
GDRIVE_PATH="gdrive:CVLab/Backups"

# Create backup
./scripts/backup-cvlab.sh --dest "$BACKUP_DIR" --exports

# Upload to Google Drive
rclone copy "$BACKUP_DIR" "$GDRIVE_PATH"

# Clean up local backups
rm -f "$BACKUP_DIR"/cvlab_backup_*.zip
```

### Monitoring and Notifications

#### Email Notification on Success/Failure

```bash
#!/bin/bash
# backup-with-email.sh

EMAIL="admin@example.com"
LOG_FILE="/tmp/cvlab-backup.log"

# Run backup and capture output
if ./scripts/backup-cvlab.sh --dest /backups/cvlab --keep 7 > "$LOG_FILE" 2>&1; then
  # Success
  mail -s "CV Lab Backup Successful" "$EMAIL" < "$LOG_FILE"
else
  # Failure
  mail -s "CV Lab Backup FAILED" "$EMAIL" < "$LOG_FILE"
fi
```

#### Slack Notification

```bash
#!/bin/bash
# backup-with-slack.sh

SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Run backup
if ./scripts/backup-cvlab.sh --dest /backups/cvlab --keep 7; then
  MESSAGE="✅ CV Lab backup completed successfully"
else
  MESSAGE="❌ CV Lab backup failed"
fi

# Send to Slack
curl -X POST "$SLACK_WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"$MESSAGE\"}"
```

### Troubleshooting

#### Script fails with "jq: command not found"
Install jq:
- macOS: `brew install jq`
- Ubuntu/Debian: `sudo apt-get install jq`
- CentOS/RHEL: `sudo yum install jq`

#### Script fails with "Connection refused"
- Verify CV Lab is running
- Check the API host and port
- Ensure firewall allows connections

#### Backup creation succeeds but download fails
- Check disk space in destination directory
- Verify write permissions
- Check network connectivity

#### Old backups not being deleted
- Verify the `--keep` option is set
- Check write permissions in backup directory
- Ensure backup filenames match pattern `cvlab_backup_*.zip`

### Security Considerations

1. **Backup Storage**: Store backups in a secure location with appropriate permissions
2. **Encryption**: Consider encrypting backups containing sensitive data
3. **Access Control**: Limit access to backup files and scripts
4. **Network Security**: Use HTTPS if accessing remote CV Lab instances
5. **Credentials**: Never store API keys or passwords in scripts

### Best Practices

1. **Test Restores**: Regularly test backup restoration
2. **Multiple Locations**: Store backups in multiple locations
3. **Retention Policy**: Keep multiple backup versions
4. **Monitoring**: Set up alerts for backup failures
5. **Documentation**: Document your backup procedures
6. **Automation**: Automate backups to ensure consistency
7. **Verification**: Verify backup integrity after creation

## Additional Resources

- [BACKUP_RESTORE_GUIDE.md](../BACKUP_RESTORE_GUIDE.md) - Complete backup and restore documentation
- [BACKUP_FEATURE_SUMMARY.md](../BACKUP_FEATURE_SUMMARY.md) - Feature implementation details
- [API Documentation](../API.md) - Full API reference
