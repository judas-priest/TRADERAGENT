#!/usr/bin/env bash
# ============================================================================
# TRADERAGENT — Automated PostgreSQL Backup
#
# Usage:
#   ./scripts/backup_db.sh              # Run backup
#   ./scripts/backup_db.sh --restore <file>  # Restore from backup
#
# Environment variables (from .env or exported):
#   DB_USER          (default: traderagent)
#   DB_PASSWORD      (default: from .env)
#   DB_NAME          (default: traderagent)
#   DB_HOST          (default: localhost)
#   DB_PORT          (default: 5432)
#   BACKUP_DIR       (default: ./backups)
#   BACKUP_RETAIN_DAYS (default: 7)
#   TELEGRAM_BOT_TOKEN    (optional — for failure alerts)
#   TELEGRAM_ALLOWED_CHAT_IDS (optional — comma-separated chat IDs)
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env if present
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

# Configuration
DB_USER="${DB_USER:-traderagent}"
DB_NAME="${DB_NAME:-traderagent}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
BACKUP_RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-7}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

# ── Telegram notification helper ──────────────────────────────────────────
send_telegram() {
    local message="$1"
    if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_ALLOWED_CHAT_IDS:-}" ]]; then
        return 0
    fi
    # Send to each chat ID
    IFS=',' read -ra CHATS <<< "$TELEGRAM_ALLOWED_CHAT_IDS"
    for chat_id in "${CHATS[@]}"; do
        chat_id="$(echo "$chat_id" | tr -d ' ')"
        curl -s -X POST \
            "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${chat_id}" \
            -d "text=${message}" \
            -d "parse_mode=Markdown" > /dev/null 2>&1 || true
    done
}

# ── Restore mode ──────────────────────────────────────────────────────────
if [[ "${1:-}" == "--restore" ]]; then
    RESTORE_FILE="${2:-}"
    if [[ -z "$RESTORE_FILE" ]]; then
        echo "Usage: $0 --restore <backup_file.sql.gz>"
        exit 1
    fi
    if [[ ! -f "$RESTORE_FILE" ]]; then
        echo "Error: Backup file not found: $RESTORE_FILE"
        exit 1
    fi

    echo "=== Restoring $DB_NAME from $RESTORE_FILE ==="
    echo "WARNING: This will DROP and recreate the database."
    read -rp "Continue? [y/N] " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        echo "Aborted."
        exit 0
    fi

    # If running inside Docker network, use container
    if docker ps --format '{{.Names}}' | grep -q traderagent-postgres; then
        echo "Restoring via Docker container..."
        # Drop and recreate
        docker exec traderagent-postgres \
            psql -U "$DB_USER" -d postgres \
            -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
        docker exec traderagent-postgres \
            psql -U "$DB_USER" -d postgres \
            -c "DROP DATABASE IF EXISTS $DB_NAME;"
        docker exec traderagent-postgres \
            psql -U "$DB_USER" -d postgres \
            -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
        # Restore
        gunzip -c "$RESTORE_FILE" | docker exec -i traderagent-postgres \
            psql -U "$DB_USER" -d "$DB_NAME" --quiet
    else
        echo "Restoring via psql..."
        export PGPASSWORD="${DB_PASSWORD:-}"
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
            -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
            -c "DROP DATABASE IF EXISTS $DB_NAME;"
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres \
            -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
        gunzip -c "$RESTORE_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" --quiet
    fi

    echo "=== Restore complete ==="
    exit 0
fi

# ── Backup mode (default) ────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"

echo "=== PostgreSQL Backup: $DB_NAME ==="
echo "Timestamp: $TIMESTAMP"
echo "Output:    $BACKUP_FILE"

# Try Docker container first, fall back to local pg_dump
if docker ps --format '{{.Names}}' | grep -q traderagent-postgres; then
    echo "Using Docker container pg_dump..."
    if ! docker exec traderagent-postgres \
        pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges \
        | gzip > "$BACKUP_FILE"; then
        send_telegram "🔴 *TRADERAGENT Backup FAILED*%0A%0ADatabase: \`$DB_NAME\`%0ATime: $TIMESTAMP%0AError: pg_dump via Docker failed"
        echo "ERROR: pg_dump failed"
        exit 1
    fi
else
    echo "Using local pg_dump..."
    export PGPASSWORD="${DB_PASSWORD:-}"
    if ! pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-privileges | gzip > "$BACKUP_FILE"; then
        send_telegram "🔴 *TRADERAGENT Backup FAILED*%0A%0ADatabase: \`$DB_NAME\`%0ATime: $TIMESTAMP%0AError: pg_dump failed"
        echo "ERROR: pg_dump failed"
        exit 1
    fi
fi

# Verify backup file is non-empty
BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null || echo 0)
if [[ "$BACKUP_SIZE" -lt 100 ]]; then
    send_telegram "🔴 *TRADERAGENT Backup FAILED*%0A%0ADatabase: \`$DB_NAME\`%0ATime: $TIMESTAMP%0AError: Backup file too small (${BACKUP_SIZE} bytes)"
    echo "ERROR: Backup file too small: $BACKUP_SIZE bytes"
    rm -f "$BACKUP_FILE"
    exit 1
fi

echo "Backup size: $(numfmt --to=iec "$BACKUP_SIZE" 2>/dev/null || echo "${BACKUP_SIZE} bytes")"

# ── Cleanup old backups ──────────────────────────────────────────────────
DELETED=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$BACKUP_RETAIN_DAYS" -delete -print | wc -l)
if [[ "$DELETED" -gt 0 ]]; then
    echo "Cleaned up $DELETED old backup(s) (retention: ${BACKUP_RETAIN_DAYS} days)"
fi

TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" | wc -l)

echo "=== Backup complete ==="
echo "Backups on disk: $TOTAL_BACKUPS"

# Success notification (optional, only if Telegram is configured)
send_telegram "✅ *TRADERAGENT Backup OK*%0A%0ADatabase: \`$DB_NAME\`%0ASize: $(numfmt --to=iec "$BACKUP_SIZE" 2>/dev/null || echo "${BACKUP_SIZE}B")%0ARetained: ${TOTAL_BACKUPS} backups"
