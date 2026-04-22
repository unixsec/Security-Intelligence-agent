# 编译与打包指南

本文介绍如何从源码构建 SIA 的两个容器镜像（`sia-backend`、`sia-web`），适用于 CI 流水线和本地快速验证。

真正的部署流程见 [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) —— `scripts/deploy/deploy-k8s.sh` 会自动调用本文描述的构建步骤。

## 1. 先决条件

| 工具 | 版本 | 用途 |
|---|---|---|
| Docker | ≥ 24（启用 BuildKit） | 构建镜像 |
| Node.js | 22 LTS | 前端构建（若本地构建前端） |
| Python | 3.12（可选） | 本地运行单元测试 |
| git | 任意 | 源码管理（镜像 tag 默认用 git short SHA） |

Linux 构建环境（可选本地运行 WeasyPrint 生成 PDF 时）需要：
```bash
apt-get install -y libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev pkg-config
```
容器运行时只需要对应的 `libcairo2` / `libpango-1.0-0` / `libgdk-pixbuf2.0-0`（Dockerfile 已包含）。

## 2. 镜像

### 2.1 后端 `sia-backend`

**文件**：`deploy/docker/Dockerfile`
**基镜像**：`python:3.12-slim`（多阶段构建，运行时无编译工具链）
**入口**：`tini -- uvicorn sia.main:app --host 0.0.0.0 --port 8080 --workers 4 --loop uvloop`
**运行身份**：UID 1000（`sia`），`readOnlyRootFilesystem` 兼容（可写目录在 K8s 端用 emptyDir 挂载）

默认镜像同时用于 `sia-api` Deployment 和 `sia-consumer` Deployment，差异仅在 K8s 层 `command/args`。

### 2.2 前端 `sia-web`

**文件**：`deploy/docker/Dockerfile.web`
**基镜像**：`nginxinc/nginx-unprivileged:1.27-alpine`（非 root nginx，默认 UID 101）
**监听**：`:8080`
**作用**：静态 SPA 提供 + `/api/*` 反向代理到 `sia-api:8080` 内部 Service

## 3. 本地构建

### 3.1 一键（推荐）

通过部署脚本间接构建 —— `deploy-k8s.sh` 在 `--skip-build` 未指定时自动执行：

```bash
./scripts/deploy/deploy-k8s.sh --skip-push --dry-run
# 会构建本地镜像但不推送、不真正部署
```

### 3.2 手工 docker build

```bash
# 启用 BuildKit，支持缓存导入
export DOCKER_BUILDKIT=1

# 后端
docker build \
  -f deploy/docker/Dockerfile \
  -t sia-backend:0.2.0 \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  .

# 前端（构建上下文是仓库根，不是 web/）
docker build \
  -f deploy/docker/Dockerfile.web \
  -t sia-web:0.2.0 \
  .
```

### 3.3 多架构（amd64 + arm64）

```bash
docker buildx create --name sia-builder --use --bootstrap
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f deploy/docker/Dockerfile \
  -t <REGISTRY>/sia-backend:0.2.0 \
  --push .
```

CI 流水线 (`.github/workflows/deploy.yml`) 默认用 buildx 发布 amd64 + arm64。

## 4. 验证构建产物

### 4.1 体积
```bash
docker images | grep -E "sia-(backend|web)"
# 期望：
# sia-backend   ~ 700 MB（含 torch/sentence-transformers；可按需剔除）
# sia-web       ~  45 MB
```

### 4.2 以非 root 运行
```bash
docker run --rm --read-only --tmpfs /tmp --tmpfs /home/sia/.cache \
  sia-backend:0.2.0 id
# 预期：uid=1000(sia) gid=1000(sia)

docker run --rm sia-web:0.2.0 id
# 预期：uid=101(nginx) gid=101(nginx)
```

### 4.3 CVE 扫描（CI 已接入 Trivy）
```bash
trivy image --severity HIGH,CRITICAL --ignore-unfixed sia-backend:0.2.0
trivy image --severity HIGH,CRITICAL --ignore-unfixed sia-web:0.2.0
```
CI 在发现 HIGH+CRITICAL 未修复漏洞时会中断流水线。

### 4.4 镜像签名验证（生产）
```bash
cosign verify <REGISTRY>/sia-backend@sha256:<digest> \
  --certificate-identity=https://github.com/<OWNER>/<REPO>/.github/workflows/deploy.yml@refs/tags/v0.2.0 \
  --certificate-oidc-issuer=https://token.actions.githubusercontent.com
```
cosign keyless 签名链路在 `.github/workflows/deploy.yml` 中启用；企业内 Fulcio/Rekor 可替换。

## 5. 推送到私有仓库

```bash
docker login <REGISTRY>
docker tag sia-backend:0.2.0 <REGISTRY>/sia-backend:0.2.0
docker push <REGISTRY>/sia-backend:0.2.0
docker tag sia-web:0.2.0     <REGISTRY>/sia-web:0.2.0
docker push <REGISTRY>/sia-web:0.2.0
```

`deploy-k8s.sh` 会在检测到 `registry.url` 后自动打 tag 并推送。

## 6. 开发循环（本地，无 K8s）

适合只跑后端单元测试，不验证 K8s 部署：

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# 本地基础设施（MySQL + Redis）
export DEV_MYSQL_ROOT_PASSWORD=$(openssl rand -base64 24)
export DEV_MYSQL_PASSWORD=$(openssl rand -base64 24)
docker compose up -d

# 必要环境变量（生产校验之外的最小集）
export SIA_ENV=dev
export SIA_MYSQL_PASSWORD="$DEV_MYSQL_PASSWORD"
export SIA_AUTH_JWT_SECRET=$(openssl rand -hex 32)
export SIA_API_KEY=$(openssl rand -hex 32)

# 单测
PYTHONPATH=src pytest tests/unit -q

# 启动 API（热重载）
PYTHONPATH=src uvicorn sia.main:app --reload --port 8080
```

前端本地开发：
```bash
cd web
npm install
npm run dev    # Vite dev server 于 http://localhost:3000
```

## 7. CI 构建摘要

`.github/workflows/ci.yml` 在每次 push/PR 触发：

1. `lint` — ruff check + format
2. `personal-info-lint` — 拦截 MBP / 个人凭据 / 弱默认值进仓库
3. `test` — MySQL + Redis service container，pytest
4. `build-backend` — 构建 + Trivy 扫描（HIGH+ 阻断）
5. `build-web` — 同上
6. `helm-lint`

`.github/workflows/deploy.yml` 在打 `v*` tag 或手动触发时：

1. 多架构构建 + 推送
2. Trivy 镜像扫描
3. Syft 生成 CycloneDX SBOM
4. Cosign keyless 签名 + SBOM attestation
5. Helm 部署到目标环境

## 8. 常见问题

| 症状 | 原因 | 解决 |
|---|---|---|
| `weasyprint` 构建失败 | 缺系统依赖 | Dockerfile 已装；本地需装 `libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev` |
| `sentence-transformers` 下载模型超时 | 网络受限 | 挂 emptyDir 到 `/home/sia/.cache`，或预下载并 COPY 进镜像 |
| nginx 启动失败 `permission denied` | 试图绑定 < 1024 | 检查 nginx.conf `listen 8080`（不是 80） |
| 镜像 tag 是 git short SHA 不可预期 | 未显式传 `-t` | 使用 `./scripts/deploy/deploy-k8s.sh -t v0.2.0` |
| Alembic autogenerate 不检测变更 | 模型未导入 | `src/sia/models/__init__.py` 需 `from .intelligence import *` 等 |

## 9. 版本变更

每次发布新版本：

1. 改 `pyproject.toml`、`src/sia/__init__.py`、`deploy/helm/sia/Chart.yaml`、`deploy/docker/Dockerfile` 中的版本号
2. `git tag v0.x.y && git push --tags` 触发 `deploy.yml`
3. 更新 [`CHANGELOG`](../CHANGELOG.md)（若有）

---

*SIA v0.2.0 | Build & Package Guide*
