# Changelog

All notable changes to SIA. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — Enterprise hardening (Top-5 must-fix from ARCHITECTURE_REVIEW.md)
- **SSRF defence** in Collector: new `src/sia/collector/url_validator.py` rejects
  non-http(s) schemes, loopback/RFC1918/link-local (cloud metadata) IPs, and
  over-long URLs. `fetcher.py` now disables auto-redirect and re-validates each
  hop; response size cap (20 MiB) and Content-Type whitelist enforced.
- **Distributed lock for scheduler** (`src/sia/scheduler/distributed_lock.py`):
  Redis `SET NX EX` + token-guarded Lua DEL implements a redlock-lite so only
  one `sia-api` replica runs each cron. All four jobs decorated with
  `@with_leader_lock`.
- **Audit hash chain** (`src/sia/common/audit.py`): `audit()` now persists to
  the `audit_log` table with a SHA-256 chain; `scripts/ops/verify_audit_chain.py`
  walks the chain and exits non-zero on any break (run daily).
- **Outbox Publisher** (`src/sia/common/outbox.py`): long-running drain task
  started alongside the analyzer; `SELECT … FOR UPDATE SKIP LOCKED` for
  multi-publisher safety; exponential retry; capped at 5 attempts before
  moving rows to `failed`.
- **Backup / DR tooling**:
  - `scripts/ops/backup_mysql.sh` — full dump + SHA-256 sidecar
  - `scripts/ops/restore_mysql.sh` — stage-then-swap with verification
  - `scripts/ops/rebuild_vectors.py` — rebuild Milvus from MySQL
  - `scripts/ops/reconcile_analyzing.py` — re-queue orphaned analyzing rows
  - `scripts/ops/dr_drill.sh` — end-to-end sandbox drill with RTO measurement
  - `docs/RUNBOOKS/DR.md` — 5-class DR playbook (outage / data loss / NS /
    region / drill), explicit RPO/RTO per tier.
- Unit tests: `test_url_validator.py`, `test_distributed_lock.py`,
  `test_audit_chain.py`, `test_outbox.py` (+36 tests, patterns covered).
- `docs/ARCHITECTURE_REVIEW.md` — Chief Architect enterprise-readiness review
  (20 code-level claims verified + 10 architecture-level gap dimensions +
  prioritised roadmap).

### Added — License
- `LICENSE` file (Apache License 2.0). Project license changed from `Proprietary` to `Apache-2.0`.
- Image labels `org.opencontainers.image.licenses=Apache-2.0` and `org.opencontainers.image.source` on both backend and web images.
- Helm Chart `annotations.licenses: Apache-2.0` and `sources` pointing to the upstream repo.

### Changed
- `pyproject.toml` `license = {text = "Apache-2.0"}` (+ `license-files`).
- `web/package.json` `"license": "Apache-2.0"`.
- `README.md` now shows the Apache 2.0 notice block.

---

## [0.2.0] — 2026-04-22

### Added
- Centralized deployment configuration: `deploy/deployment.config.example.yaml` + `scripts/deploy/configure.sh` renderer.
- Enterprise Kubernetes deployment script `scripts/deploy/deploy-k8s.sh` with build, push, Secret apply, helm upgrade, and post-deploy smoke test.
- Structured audit logger `sia.common.audit.audit()` emitting JSON events on a dedicated `sia.audit` logger.
- Logging redaction filter `sia.common.logging_redact` that scrubs secrets from app + SQLAlchemy + httpx log output.
- RS256 JWT support (alongside HS256) with automatic keypair generation via `configure.sh --generate-secrets`.
- Per-identity rate limiting (JWT / API-Key / IP) and a stricter 5 req/min/IP bucket on login endpoints.
- TLS to MySQL / Redis via CA Secret mount at `/etc/sia/tls/`.
- Graceful shutdown of the analysis consumer on SIGTERM / SIGINT.
- Optional Falco runtime rules ConfigMap (`security.falcoRulesEnabled`).
- Optional OPA Gatekeeper sample constraints under `deploy/k8s/gatekeeper-constraints/` (`readOnlyRootFS`, required resources, block `:latest`).
- Dependabot config for pip / npm / docker / actions.
- CI workflow: Trivy image scan (HIGH+ blocks), Syft SBOM, Cosign keyless signing + SBOM attestation.
- CI `personal-info-lint` step to prevent developer-specific strings from entering the repo.
- Documentation set: `ARCHITECTURE.md`, `BUILD_GUIDE.md`, `DEPLOYMENT_GUIDE.md`, `CONFIGURATION.md`, `OPERATIONS_GUIDE.md`, `SECURITY.md`, `USER_MANUAL.md`, `API_REFERENCE.md`, root `README.md`.

### Changed
- Kubernetes pods and jobs are now hardened:
  - Container-level `securityContext`: `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile.type: RuntimeDefault`.
  - Writable cache paths (`/tmp`, `/home/sia/.cache`, `/var/run`) provisioned as `emptyDir`.
  - `topologySpreadConstraints` on all Deployments.
- Frontend image now uses `nginxinc/nginx-unprivileged` and listens on port 8080 as UID 101.
- Secrets are mounted as read-only files under `/etc/sia/secrets/` (mode `0400`); the application reads them via `SIA_SECRETS_DIR`. Secrets no longer ride on `envFrom`.
- Consumer `terminationGracePeriodSeconds` raised to 90.
- `NetworkPolicy` egress on port 80/443 is now parameterized by `network.egressAllowedCidrs`.
- `docker-compose.yaml` requires `DEV_MYSQL_ROOT_PASSWORD` / `DEV_MYSQL_PASSWORD` / (optional) `DEV_REDIS_PASSWORD` env vars — no defaults.

### Removed
- **Breaking**: committer-specific local development docs and scripts (Parallels/macOS VM provisioning, `connect-dev.sh`, `provision-dev-server.sh`, `setup-sia.sh`, `LOCAL_TEST_PLAN.md`, `ISOLATED_DEV_ENV.md`, `LOCAL_MBP_PARALLELS_DEV.md`, `docs/legacy/`). Use the enterprise K8s flow.
- All hardcoded default credentials (`sia_dev_pass`, `root_dev_pass`, `minioadmin:minioadmin`, `change-me-in-production` JWT default). Missing secrets in production now fail startup.
- Stale personal entries from `.claude/settings.local.json`.

### Security
- CRITICAL: default JWT signing key removed; production requires `SIA_AUTH_JWT_SECRET` (≥32 bytes) or RS256 keypair.
- CRITICAL: production aborts startup if MySQL password or MinIO credentials are empty / left at known defaults.
- HIGH: API Key path now reads from mounted secret file; no environment exposure.
- Full audit (20 items) tracked in `docs/SECURITY.md` §2.

---

## [0.1.0] — 2026-03-29

Initial release.
