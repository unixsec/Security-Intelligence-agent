# Changelog

All notable changes to SIA. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/).

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
