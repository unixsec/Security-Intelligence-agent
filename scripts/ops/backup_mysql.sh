#!/bin/bash
# Backup SIA's MySQL database to compressed archive (ARCHITECTURE_REVIEW §C1).
#
# Usage:
#   ./scripts/ops/backup_mysql.sh [OUT_DIR]
# Env:
#   SIA_MYSQL_HOST, SIA_MYSQL_PORT, SIA_MYSQL_USER, SIA_MYSQL_PASSWORD, SIA_MYSQL_DATABASE
# Output:
#   OUT_DIR/sia-mysql-<YYYYMMDD-HHMMSS>.sql.gz  (gzipped, ~10% of DB size)
#
# Design notes:
#   - Uses --single-transaction for consistent snapshot on InnoDB (no table lock)
#   - Includes routines, events, triggers for full schema
#   - --set-gtid-purged=OFF to make restore portable across servers
#   - RPO: platform's PITR (binlogs) remains authoritative; this script provides
#     a full snapshot that complements PITR and can be archived off-site.
set -euo pipefail

OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"

: "${SIA_MYSQL_HOST:?SIA_MYSQL_HOST not set}"
: "${SIA_MYSQL_PORT:=3306}"
: "${SIA_MYSQL_USER:?SIA_MYSQL_USER not set}"
: "${SIA_MYSQL_PASSWORD:?SIA_MYSQL_PASSWORD not set}"
: "${SIA_MYSQL_DATABASE:?SIA_MYSQL_DATABASE not set}"

TS=$(date +%Y%m%d-%H%M%S)
OUT_FILE="${OUT_DIR}/sia-mysql-${TS}.sql.gz"
CHECK_FILE="${OUT_FILE}.sha256"

echo "[backup_mysql] $SIA_MYSQL_DATABASE → $OUT_FILE"
mysqldump \
  --host="$SIA_MYSQL_HOST" \
  --port="$SIA_MYSQL_PORT" \
  --user="$SIA_MYSQL_USER" \
  --password="$SIA_MYSQL_PASSWORD" \
  --single-transaction \
  --routines --events --triggers \
  --set-gtid-purged=OFF \
  --databases "$SIA_MYSQL_DATABASE" \
  | gzip -9 > "$OUT_FILE"

# Integrity checksum so restore can verify
sha256sum "$OUT_FILE" > "$CHECK_FILE"

SIZE=$(du -h "$OUT_FILE" | cut -f1)
echo "[backup_mysql] OK: $OUT_FILE ($SIZE)"
echo "[backup_mysql] checksum: $CHECK_FILE"
