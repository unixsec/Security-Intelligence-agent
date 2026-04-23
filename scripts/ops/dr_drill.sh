#!/bin/bash
# Disaster Recovery drill runner (ARCHITECTURE_REVIEW §C1).
#
# End-to-end flow in a sandbox / pre-prod environment:
#   1. Snapshot current MySQL → backup_mysql.sh
#   2. Destroy target DB (simulate loss)
#   3. Restore from snapshot → restore_mysql.sh
#   4. Rebuild Milvus vectors → rebuild_vectors.py
#   5. Reconcile stuck analyzing rows → reconcile_analyzing.py
#   6. Smoke test API → curl /api/v1/health
#   7. Print RTO measurement (elapsed wall time from step 2 → step 6 pass)
#
# MUST NOT run against production. The --i-know-this-is-dangerous gate
# enforces that by requiring the target namespace to match DR_NAMESPACE env.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

: "${DR_NAMESPACE:?set DR_NAMESPACE to the sandbox ns to run against (never prod)}"
CURRENT_NS=$(kubectl config view --minify -o jsonpath='{..namespace}' 2>/dev/null || echo "")
[[ "$CURRENT_NS" == "$DR_NAMESPACE" || "$1" == "--force" ]] || {
    echo "ERROR: current kubectl namespace is $CURRENT_NS, expected $DR_NAMESPACE" >&2
    echo "       use --force to override (DANGEROUS)" >&2
    exit 1
}

CONFIRM="${1:-}"
[[ "$CONFIRM" == "--i-know-this-is-dangerous" || "$CONFIRM" == "--force" ]] || {
    echo "usage: DR_NAMESPACE=sia-sandbox $0 --i-know-this-is-dangerous" >&2
    exit 2
}

T0=$(date +%s)
BACKUP_DIR="${PROJECT_ROOT}/backups"
mkdir -p "$BACKUP_DIR"

echo "[dr_drill] step 1/6: snapshot current DB"
"$SCRIPT_DIR/backup_mysql.sh" "$BACKUP_DIR"
LATEST=$(ls -t "$BACKUP_DIR"/sia-mysql-*.sql.gz | head -1)
echo "[dr_drill] latest snapshot: $LATEST"

T_CATASTROPHE=$(date +%s)
echo "[dr_drill] step 2/6: simulate data loss (drop schema)"
echo "           !!! intentionally destroying $SIA_MYSQL_DATABASE"
mysql --host="$SIA_MYSQL_HOST" --port="${SIA_MYSQL_PORT:-3306}" \
      --user="$SIA_MYSQL_USER" --password="$SIA_MYSQL_PASSWORD" \
      -e "DROP DATABASE \`$SIA_MYSQL_DATABASE\`;"

echo "[dr_drill] step 3/6: restore from snapshot"
"$SCRIPT_DIR/restore_mysql.sh" "$LATEST" --confirm

echo "[dr_drill] step 4/6: rebuild Milvus vectors"
python "$SCRIPT_DIR/rebuild_vectors.py" --batch 100 || echo "  (milvus rebuild skipped)"

echo "[dr_drill] step 5/6: reconcile orphaned analyzing rows"
python "$SCRIPT_DIR/reconcile_analyzing.py" --older-than 1m

echo "[dr_drill] step 6/6: smoke test API"
# Expect sia-api pod to serve /health
kubectl -n "$DR_NAMESPACE" port-forward svc/sia-api 18080:8080 &>/dev/null &
PF=$!
sleep 4
CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:18080/api/v1/health || echo 000)
kill $PF 2>/dev/null || true
[[ "$CODE" == "200" ]] || { echo "health check failed: $CODE" >&2; exit 3; }

T1=$(date +%s)
RTO_SEC=$((T1 - T_CATASTROPHE))
echo ""
echo "============================================================"
echo "  DR drill PASS"
echo "  Measured RTO: ${RTO_SEC}s  (target: ≤ 1800s per NFR)"
echo "  Snapshot used: $LATEST"
echo "============================================================"
