# Security Intelligence Agent (SIA)

> ⚠️ **Early Access (v0.x)** — Production deployment requires the hardening checklist in [`docs/SECURITY.md`](./docs/SECURITY.md) §11. Defaults are tuned for try-out, not for hostile environments.

**v0.2.0** — AI-powered security intelligence aggregation & analysis platform, designed to run on enterprise Kubernetes.

SIA continuously ingests security intelligence from public and internal sources, uses LLMs to enrich and triage each item, and delivers prioritized daily / weekly / emergency reports through a Web console, REST API, and email.

## Highlights

- **One-click K8s deployment** — a single `deployment.config.yaml` + two scripts
- **Hardened by default** — `readOnlyRootFilesystem`, dropped capabilities, non-root UIDs, secrets mounted as files, TLS to datastores
- **Multi-LLM with failover** — Anthropic / OpenAI / Google / local OpenAI-compatible, with per-model circuit breakers + on-egress anonymization
- **Structured audit** — every sensitive action emits a JSON event on a dedicated `sia.audit` logger
- **Supply-chain aware** — CI runs Trivy scans, generates SBOMs (Syft) and signs images (Cosign keyless)

## Quick start (deploy)

```bash
cp deploy/deployment.config.example.yaml deployment.config.yaml
$EDITOR deployment.config.yaml                        # fill placeholders
./scripts/deploy/configure.sh --generate-secrets      # render values + Secret
./scripts/deploy/deploy-k8s.sh                        # build + push + helm + smoke
```

Full walkthrough: [`docs/DEPLOYMENT_GUIDE.md`](./docs/DEPLOYMENT_GUIDE.md).

## Documentation

| Doc | 简介 |
|---|---|
| [`docs/README.md`](./docs/README.md) | Documentation index |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | System architecture & data flow |
| [`docs/BUILD_GUIDE.md`](./docs/BUILD_GUIDE.md) | Build images from source |
| [`docs/DEPLOYMENT_GUIDE.md`](./docs/DEPLOYMENT_GUIDE.md) | Enterprise K8s deployment (authoritative ops doc) |
| [`docs/CONFIGURATION.md`](./docs/CONFIGURATION.md) | Placeholder / env-var / Helm values reference |
| [`docs/OPERATIONS_GUIDE.md`](./docs/OPERATIONS_GUIDE.md) | Day-2 ops, scaling, rollback, incident response |
| [`docs/SECURITY.md`](./docs/SECURITY.md) | Threat model, hardening baseline, compliance |
| [`docs/USER_MANUAL.md`](./docs/USER_MANUAL.md) | Web console user guide |
| [`docs/API_REFERENCE.md`](./docs/API_REFERENCE.md) | REST API reference & integration examples |

## Source layout

```
.
├── src/sia/                Python backend (FastAPI + consumer)
├── web/                    Vue 3 frontend (Vite + Element Plus + Pinia + ECharts)
├── config/                 auth.yaml, llm_gateway.yaml (non-secret)
├── prompts/                LLM prompt templates
├── workflows/              YAML workflow definitions
├── migrations/             alembic
├── deploy/
│   ├── docker/             Dockerfile(.web), nginx.conf
│   ├── helm/sia/           Helm chart (values.yaml, templates/)
│   ├── k8s/                Optional Gatekeeper constraints
│   └── deployment.config.example.yaml
├── scripts/
│   ├── deploy/             configure.sh, deploy-k8s.sh
│   └── ops/                init_db, seed_sources, init_admin, etc.
├── tests/                  pytest (unit / integration / e2e / smoke)
├── .github/workflows/      CI + deploy pipelines
└── docs/                   (see table above)
```

## Versioning

- Chart + app version live in `pyproject.toml`, `src/sia/__init__.py`, `deploy/helm/sia/Chart.yaml`, `deploy/docker/Dockerfile`
- Bump all four when tagging a release

## Security contact

Report vulnerabilities via the channel your deployment team published in `docs/SECURITY.md` §10. Please do **not** open public issues for unpatched security findings.

## License

Licensed under the **[Apache License 2.0](./LICENSE)**.

```
Copyright 2026 alex <unix_sec@163.com>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
