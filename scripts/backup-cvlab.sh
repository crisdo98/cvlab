#!/bin/bash
#
# CV Lab Automated Backup Script
#
# This script creates a backup of CV Lab data and optionally
# copies it to an external location for safekeeping.
#
# Usage:
#   ./scripts/backup-cvlab.sh [OPTIONS]
#
# Options:
#   -h, --host HOST       API host (default: localhost:8000)
#   -d, --dest DIR        Destination directory for backups
#   -e, --exports         Include exported files in backup
#   -k, --keep N          Keep only the last N backups (default: 7)
#   -v, --verbose         Verbose output
#   --help                Show this help message
#

set -e

# Default values
API_HOST="localhost:8000"
DEST_DIR=""
INCLUDE_EXPORTS="false"
KEEP_BACKUPS=7
VERBOSE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--host)
      API_HOST="$2"
      shift 2
      ;;
    -d|--dest)
      DEST_DIR="$2"
      shift 2
      ;;
    -e|--exports)
      INCLUDE_EXPORTS="true"
      shift
      ;;
    -k|--keep)
      KEEP_BACKUPS="$2"
      shift 2
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    --help)
      head -n 20 "$0" | tail -n +2 | sed 's/^# //'
      exit 0
      ;;
    *)
      echo -e "${RED}Error: Unknown option $1${NC}"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Logging functions
log_info() {
  echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_verbose() {
  if [ "$VERBOSE" = true ]; then
    echo -e "[DEBUG] $1"
  fi
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
  log_error "jq is required but not installed. Please install jq first."
  log_info "On macOS: brew install jq"
  log_info "On Ubuntu/Debian: sudo apt-get install jq"
  exit 1
fi

# Check if curl is installed
if ! command -v curl &> /dev/null; then
  log_error "curl is required but not installed."
  exit 1
fi

# Main backup process
log_info "Starting CV Lab backup process..."
log_verbose "API Host: $API_HOST"
log_verbose "Include Exports: $INCLUDE_EXPORTS"
log_verbose "Keep Backups: $KEEP_BACKUPS"

# Create backup via API
log_info "Creating backup..."
RESPONSE=$(curl -s -X POST "http://${API_HOST}/api/backup/create" \
  -H "Content-Type: application/json" \
  -d "{\"include_exports\": ${INCLUDE_EXPORTS}}")

# Check if request was successful
if [ $? -ne 0 ]; then
  log_error "Failed to create backup. Is the CV Lab service running?"
  exit 1
fi

# Extract filename from response
FILENAME=$(echo "$RESPONSE" | jq -r '.filename')
if [ "$FILENAME" = "null" ] || [ -z "$FILENAME" ]; then
  log_error "Failed to create backup. Response: $RESPONSE"
  exit 1
fi

log_info "Backup created: $FILENAME"

# Download backup if destination directory is specified
if [ -n "$DEST_DIR" ]; then
  log_info "Downloading backup to $DEST_DIR..."
  
  # Create destination directory if it doesn't exist
  mkdir -p "$DEST_DIR"
  
  # Download backup
  curl -s -o "${DEST_DIR}/${FILENAME}" "http://${API_HOST}/api/backup/download/${FILENAME}"
  
  if [ $? -eq 0 ]; then
    log_info "Backup downloaded successfully"
    
    # Get file size
    FILE_SIZE=$(du -h "${DEST_DIR}/${FILENAME}" | cut -f1)
    log_info "Backup size: $FILE_SIZE"
    
    # Clean up old backups
    if [ "$KEEP_BACKUPS" -gt 0 ]; then
      log_info "Cleaning up old backups (keeping last $KEEP_BACKUPS)..."
      
      cd "$DEST_DIR"
      BACKUP_COUNT=$(ls -1 cvlab_backup_*.zip 2>/dev/null | wc -l)
      
      if [ "$BACKUP_COUNT" -gt "$KEEP_BACKUPS" ]; then
        TO_DELETE=$((BACKUP_COUNT - KEEP_BACKUPS))
        log_verbose "Found $BACKUP_COUNT backups, deleting $TO_DELETE oldest"
        
        ls -t cvlab_backup_*.zip | tail -n "+$((KEEP_BACKUPS + 1))" | xargs rm -f
        log_info "Deleted $TO_DELETE old backup(s)"
      else
        log_verbose "Only $BACKUP_COUNT backups found, no cleanup needed"
      fi
    fi
  else
    log_error "Failed to download backup"
    exit 1
  fi
else
  log_info "No destination directory specified, backup remains on server"
  log_info "Download with: curl -O http://${API_HOST}/api/backup/download/${FILENAME}"
fi

log_info "Backup process completed successfully!"

# Print summary
echo ""
echo "=== Backup Summary ==="
echo "Filename: $FILENAME"
if [ -n "$DEST_DIR" ]; then
  echo "Location: ${DEST_DIR}/${FILENAME}"
fi
echo "Exports included: $INCLUDE_EXPORTS"
echo "======================"
