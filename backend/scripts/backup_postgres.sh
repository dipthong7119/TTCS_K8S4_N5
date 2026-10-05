#!/bin/sh
set -eu
umask 077

: "${BACKUP_DIR:=/backups}"
: "${BACKUP_RETENTION_DAYS:=14}"

case "$BACKUP_RETENTION_DAYS" in
  ''|*[!0-9]*)
    echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2
    exit 2
    ;;
esac

mkdir -p "$BACKUP_DIR"

backup_once() {
  timestamp=$(date -u +%Y%m%dT%H%M%SZ)
  destination="$BACKUP_DIR/csms-$timestamp.dump"
  temporary="$destination.tmp"

  if ! pg_dump --format=custom --no-owner --no-acl --file="$temporary"; then
    rm -f "$temporary"
    echo "Database backup failed at $timestamp" >&2
    return 1
  fi

  if ! pg_restore --list "$temporary" >/dev/null; then
    rm -f "$temporary"
    echo "Backup verification failed at $timestamp" >&2
    return 1
  fi

  mv "$temporary" "$destination"
  find "$BACKUP_DIR" -type f -name 'csms-*.dump' -mtime "+$BACKUP_RETENTION_DAYS" -delete
  echo "Verified database backup: $destination"
}

restore_backup() {
  backup_file=${1:-}
  case "$backup_file" in
    "$BACKUP_DIR"/*) ;;
    *)
      echo "Choose a backup file inside $BACKUP_DIR" >&2
      return 2
      ;;
  esac
  if [ ! -f "$backup_file" ]; then
    echo "Backup file not found: $backup_file" >&2
    return 2
  fi
  if ! pg_restore --list "$backup_file" >/dev/null; then
    echo "Backup file is not a readable PostgreSQL dump: $backup_file" >&2
    return 2
  fi

  echo "This will overwrite matching objects in database '$PGDATABASE'."
  printf "Type RESTORE to continue: "
  IFS= read -r confirmation
  if [ "$confirmation" != "RESTORE" ]; then
    echo "Restore cancelled."
    return 1
  fi

  pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error \
    --dbname="$PGDATABASE" "$backup_file"
  echo "Database restore completed from $backup_file"
}

case "${1:-loop}" in
  once)
    backup_once
    ;;
  restore)
    restore_backup "${2:-}"
    ;;
  loop)
    while :; do
      if backup_once; then
        sleep 86400
      else
        echo "Retrying database backup in 15 minutes" >&2
        sleep 900
      fi
    done
    ;;
  *)
    echo "Usage: backup_postgres.sh [loop|once|restore /backups/file.dump]" >&2
    exit 2
    ;;
esac
