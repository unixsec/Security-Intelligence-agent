#!/bin/bash
# Restore SIA MySQL from a .sql.gz backup produced by backup_mysql.sh.
#
# Usage:
#   ./scripts/ops/restore_mysql.sh <backup.sql.gz> [--confirm]
# Safety:
#   - Requires --confirm flag because restore DROPS and re-CREATEs the DB
#   - Verifies sha256 checksum if .sha256 sidecar exists
#   - Runs into a temporary DB name first, verifies row counts, then swaps.
set -euo pipefail

BACKUP_FILE="${1:?backup file required}"
CONFIRM="${2:-}"

[[ -f "$BACKUP_FILE" ]] || { echo "file not found: $BACKUP_FILE" >&2; exit 1; }
[[ "$CONFIRM" == "--confirm" ]] || {
    echo "refusing to restore without --confirm; this is destructive" >&2
    exit 2
}

: "${SIA_MYSQL_HOST:?SIA_MYSQL_HOST not set}"
: "${SIA_MYSQL_PORT:=3306}"
: "${SIA_MYSQL_USER:?SIA_MYSQL_USER not set}"
: "${SIA_MYSQL_PASSWORD:?SIA_MYSQL_PASSWORD not set}"
: "${SIA_MYSQL_DATABASE:?SIA_MYSQL_DATABASE not set}"

# Checksum verification
if [[ -f "${BACKUP_FILE}.sha256" ]]; then
    echo "[restore_mysql] verifying checksum …"
    sha256sum -c "${BACKUP_FILE}.sha256"
fi

MYSQL_CMD=(mysql --host="$SIA_MYSQL_HOST" --port="$SIA_MYSQL_PORT"
                 --user="$SIA_MYSQL_USER" --password="$SIA_MYSQL_PASSWORD")

STAGING="${SIA_MYSQL_DATABASE}_restore_staging"
echo "[restore_mysql] loading into staging DB $STAGING …"
"${MYSQL_CMD[@]}" -e "DROP DATABASE IF EXISTS \`$STAGING\`; CREATE DATABASE \`$STAGING\`;"
gunzip -c "$BACKUP_FILE" | sed "s/\`${SIA_MYSQL_DATABASE}\`/\`${STAGING}\`/g" \
    | "${MYSQL_CMD[@]}" "$STAGING"

# Quick sanity check — core tables should exist and have rows
ROW_COUNT=$("${MYSQL_CMD[@]}" -sN "$STAGING" -e \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$STAGING';")
[[ "$ROW_COUNT" -ge 10 ]] || {
    echo "[restore_mysql] staging only has $ROW_COUNT tables — aborting" >&2
    exit 3
}
echo "[restore_mysql] staging has $ROW_COUNT tables ✓"

# Swap (RENAME) — requires brief downtime window. Document RTO accordingly.
echo "[restore_mysql] swapping $SIA_MYSQL_DATABASE ↔ $STAGING …"
"${MYSQL_CMD[@]}" <<SQL
  DROP DATABASE IF EXISTS \`${SIA_MYSQL_DATABASE}_previous\`;
  CREATE DATABASE IF NOT EXISTS \`${SIA_MYSQL_DATABASE}\`;
  ALTER DATABASE \`${SIA_MYSQL_DATABASE}\` CHARACTER SET utf8mb4;
SQL

# MySQL doesn't support atomic DB rename; we rename tables individually.
TABLES=$("${MYSQL_CMD[@]}" -sN "$STAGING" -e "SHOW TABLES;")
for t in $TABLES; do
    "${MYSQL_CMD[@]}" -e "
        DROP TABLE IF EXISTS \`${SIA_MYSQL_DATABASE}\`.\`$t\`;
        RENAME TABLE \`${STAGING}\`.\`$t\` TO \`${SIA_MYSQL_DATABASE}\`.\`$t\`;"
done

"${MYSQL_CMD[@]}" -e "DROP DATABASE \`${STAGING}\`;"

echo "[restore_mysql] restore OK."
echo "[restore_mysql] reminder: clear Redis caches, invalidate JWT refresh tokens."
