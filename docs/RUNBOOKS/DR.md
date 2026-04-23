# Runbook: Disaster Recovery

Authoritative playbook when the primary SIA environment is lost (DB corruption, namespace wipe, region outage). Read end-to-end **before** an incident, not during.

Version: v0.2.1 (DR tooling added)
Last tested: _(insert drill date)_

---

## 0. Scope & RPO/RTO

| Tier | Data | RPO | RTO | Recovery path |
|---|---|---|---|---|
| Gold | `intelligence`, `users`, `audit_log` | 5 min | 30 min | MySQL PITR → `restore_mysql.sh` |
| Silver | `llm_call_log`, `outbox` | 1 h | 1 h | Full dump → `restore_mysql.sh` |
| Bronze | Milvus vectors, Redis streams/cache | Best-effort (can rebuild) | 2 h | `rebuild_vectors.py` + `reconcile_analyzing.py` |
| Tin | MinIO report PDFs | 24 h | 4 h (acceptable regen) | Re-run `generate_report` workflow from MySQL data |

RPO = max acceptable **data loss** window; RTO = max acceptable **downtime**.

---

## 1. Identify incident class

| Symptom | Class | Skip to |
|---|---|---|
| One pod crashing, HPA replacing | Normal ops | *Not a DR event* |
| `sia-api` Pod cannot connect to MySQL | DB outage | §2 |
| MySQL data corrupted / tampered | Data loss | §3 |
| Entire namespace wiped | NS-level disaster | §4 |
| Entire cluster / region down | Cross-region DR | §5 |

---

## 2. DB Transient Outage

Platform-level incident; no SIA action beyond health checks. `sia-api` lifespan logs `Redis unavailable in production — aborting startup` if both are down, restarting automatically when the platform recovers.

Confirm via platform console: your managed MySQL should page the DBA. No action needed on our end unless > 30 min (escalate to on-call).

---

## 3. Data Loss (point-in-time corruption)

Use case: someone ran `DELETE FROM intelligence` by mistake; schema change broke data; ransomware encrypted tables.

```bash
# 1. Freeze writes immediately
kubectl -n sia scale deploy/sia-api --replicas=0
kubectl -n sia scale deploy/sia-consumer --replicas=0

# 2. Restore MySQL via platform PITR to T-5min (ask DBA)
#    OR restore from daily snapshot:
./scripts/ops/restore_mysql.sh /backups/sia-mysql-<date>.sql.gz --confirm

# 3. Rebuild derived data
python scripts/ops/rebuild_vectors.py
# (MinIO reports are regenerable — skip unless needed)

# 4. Resume
kubectl -n sia scale deploy/sia-api --replicas=2
kubectl -n sia scale deploy/sia-consumer --replicas=1

# 5. Re-queue any intelligence rows that got stuck mid-analyze
python scripts/ops/reconcile_analyzing.py --older-than 30m

# 6. Verify chain
python scripts/ops/verify_audit_chain.py
```

Expected elapsed: **10 – 20 min** for a ~10 GB DB.

---

## 4. Namespace-level Disaster

Namespace was deleted; Secrets and workloads gone.

```bash
# 1. Recreate namespace
kubectl create ns sia

# 2. Restore Secret (from your sealed-secrets / Vault / external-secrets)
#    - If you still have deployment.config.yaml on the deploy host:
./scripts/deploy/configure.sh
kubectl apply -f deploy/rendered/sia-secrets.yaml
#    - Otherwise: pull from Vault / sealed-secrets repo

# 3. Deploy
./scripts/deploy/deploy-k8s.sh --skip-build --skip-push -t v0.2.0

# 4. Restore data (if platform DB is shared, skip; if DB was per-namespace, restore it)
./scripts/ops/restore_mysql.sh /backups/sia-mysql-<latest>.sql.gz --confirm

# 5. Reconcile
python scripts/ops/rebuild_vectors.py
python scripts/ops/reconcile_analyzing.py
python scripts/ops/verify_audit_chain.py

# 6. Smoke test
curl https://<INGRESS_HOST>/api/v1/health          # expect 200
curl https://<INGRESS_HOST>/api/v1/intelligence    # expect 401
```

Expected elapsed: **20 – 40 min**.

---

## 5. Region Disaster (Future — v1.0)

v0.2.0 is single-region. When a region is gone:
1. Switch DNS to DR region's Ingress host (manual today; GSLB in v1.0).
2. Promote DR MySQL replica → primary (platform-specific).
3. Deploy SIA into DR region via same `deploy-k8s.sh`.
4. Reconcile streams & vectors as §3.

Pre-requisites (must be done BEFORE a disaster):
- Cross-region MySQL replica
- MinIO cross-region bucket replication
- DR-region container registry mirror
- DR-region K8s cluster with cert-manager + ingress-nginx pre-provisioned

---

## 6. Quarterly Drill

```bash
export DR_NAMESPACE=sia-sandbox
./scripts/ops/dr_drill.sh --i-know-this-is-dangerous
```

Records RTO to stdout. Paste the line into `docs/RUNBOOKS/DR_HISTORY.md` (create on first run).

Target cadence: **once per quarter** in staging. Break-glass reviews if RTO exceeds NFR.

---

## 7. Backup verification (weekly CronJob)

```yaml
# deploy/helm/sia/templates/cronjob-backup-verify.yaml (future)
schedule: "0 4 * * 1"   # Mondays 04:00
command: [
  "python", "scripts/ops/verify_audit_chain.py",
  "&&",
  "./scripts/ops/backup_mysql.sh", "/pvc/backups"
]
```

Alert if any step fails; test is a no-op cost.

---

## 8. Contacts

| Role | Contact |
|---|---|
| DB on-call | (platform team) |
| SIA engineer | alex <unix_sec@163.com> |
| Vault / Secret admin | (platform team) |
| Network / DNS | (platform team) |

_(populate before production)_
