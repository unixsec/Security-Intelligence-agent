# 安全洞察与情报分析智能体 — 系统设计方案 v3.0

> **文档版本：** 3.0（聚焦部署便捷性、可维护性与功能测试友好性）
> **日期：** 2026-03-29
> **作者：** alex &lt;unix_sec@163.com&gt;
> **状态：** 最终稿
> **密级：** 内部机密
> **变更说明：** 在 v2.0 基础上，从 DevOps 工程师、测试工程师、一线运维三个视角深度审视，补充 42 处部署/维护/测试领域的设计不足，新增 15 个专题章节。

---

## v2.0 → v3.0 变更审计摘要

> 以下为 v2.0 经多角色审视后在 **部署便捷性、可维护性、功能测试** 三大维度发现的关键不足，v3.0 已全部修正。

### DevOps 工程师视角：16 处不足

| # | 问题 | v2.0 现状 | v3.0 修正 |
|---|------|----------|----------|
| DO-1 | **无 IaC（基础设施即代码）** | 仅零散 YAML 片段，无统一部署包 | 新增§32.1 Helm Chart 完整设计（values.yaml 分层覆盖） |
| DO-2 | **无 Dockerfile / 容器构建策略** | 未定义镜像构建方式 | 新增§32.2 多阶段 Dockerfile + 镜像仓库管理 |
| DO-3 | **无本地开发环境** | 开发必须连 K8s 集群 | 新增§32.3 docker-compose 本地开发环境（一键启动全栈） |
| DO-4 | **无 CI/CD Pipeline 设计** | 仅提到 CI Gate 概念 | 新增§33 完整 CI/CD Pipeline（GitLab CI/GitHub Actions 双版本） |
| DO-5 | **无环境管理策略** | 未区分 dev/staging/prod | 新增§32.4 三环境分层（dev/staging/prod）+ 配置覆盖策略 |
| DO-6 | **无数据库迁移方案** | Schema 直接给 DDL，无版本管理 | 新增§34.1 Alembic 数据库迁移 + Schema 版本化 |
| DO-7 | **无 Secrets 管理** | "用环境变量"一笔带过 | 新增§34.2 K8s Sealed Secrets / Vault 方案 |
| DO-8 | **无 GitOps 工作流** | 提及 GitOps 但无设计 | 新增§33.4 ArgoCD GitOps 部署流程 |
| DO-9 | **无一键部署脚本** | 无 Makefile / 部署脚本 | 新增§32.5 Makefile + 部署自动化脚本 |
| DO-10 | **无镜像版本策略** | 未定义 tag 规范 | 新增§32.2 镜像 tag 策略（Git SHA + SemVer） |
| DO-11 | **无 K8s 资源模板化** | 硬编码资源限制 | §32.1 Helm values.yaml 按环境覆盖 |
| DO-12 | **无部署前置检查** | 无 pre-deploy 验证 | 新增§33.3 部署前置检查清单（自动化） |
| DO-13 | **无回滚标准流程** | 仅提到"回滚 canary" | 新增§34.3 一键回滚 SOP（Helm rollback + DB 兼容） |
| DO-14 | **无依赖服务启动顺序** | 服务启动无编排 | 新增§32.6 K8s initContainers 依赖等待 |
| DO-15 | **无 Grafana Dashboard 即代码** | 提到仪表盘但无模板 | 新增§34.4 Grafana Dashboard JSON 模板 + Provisioning |
| DO-16 | **无日志采集管线** | 提到 Loki 但无管线设计 | 新增§34.5 Promtail → Loki 日志采集管线 |

### 测试工程师视角：18 处不足

| # | 问题 | v2.0 现状 | v3.0 修正 |
|---|------|----------|----------|
| TE-1 | **无测试环境架构** | 未设计隔离测试环境 | 新增§35.1 测试环境架构（共享 vs 隔离 vs 临时环境） |
| TE-2 | **无 Mock/Stub 策略** | 测试如何 Mock LLM 未定义 | 新增§35.2 外部依赖 Mock 策略（LLM/企微/飞书/NVD 全覆盖） |
| TE-3 | **无测试数据工厂** | 测试数据管理缺失 | 新增§35.3 TestDataFactory + Fixtures 设计 |
| TE-4 | **无集成测试基础设施** | testcontainers 一笔带过 | 新增§35.4 Testcontainers 集成测试架构 |
| TE-5 | **无 API 契约测试** | 服务间接口无契约保障 | 新增§35.5 OpenAPI Spec + 契约测试 |
| TE-6 | **无前端测试策略** | Vue 前端完全未涉及测试 | 新增§35.6 前端测试策略（Vitest + Playwright） |
| TE-7 | **无测试覆盖率要求** | 无覆盖率指标和追踪 | 新增§36.1 测试覆盖率标准 + CI 门控 |
| TE-8 | **无冒烟测试设计** | 部署后无验证机制 | 新增§36.2 部署后冒烟测试（自动化） |
| TE-9 | **无性能测试场景** | Locust/K6 一句话带过 | 新增§36.3 性能测试场景（含脚本模板） |
| TE-10 | **无测试报告与度量** | 测试结果无汇总分析 | 新增§36.4 测试报告仪表盘 + 趋势追踪 |
| TE-11 | **无 Dify Workflow 测试策略** | Dify Workflow 不可测试 | 新增§35.7 Dify Workflow 测试方案 |
| TE-12 | **无测试夹具清理机制** | 测试数据残留问题 | §35.3 TestDataFactory 含自动清理 |
| TE-13 | **功能测试无分层执行** | E2E 场景矩阵但无分层 | 新增§36.5 测试金字塔执行策略 |
| TE-14 | **无 LLM Mock Server** | LLM 测试必须调用真实模型 | 新增§35.2 LLM Mock Server（可重放/确定性输出） |
| TE-15 | **无消息队列测试策略** | Redis Streams 测试未覆盖 | 新增§35.8 Redis Streams 测试辅助工具 |
| TE-16 | **无多语言翻译测试** | 翻译质量无测试 | 新增§36.6 多语言处理测试用例集 |
| TE-17 | **无安全功能测试** | 安全测试仅提 Trivy + ZAP | 新增§36.7 安全功能测试场景 |
| TE-18 | **无测试环境数据脱敏** | 测试用生产数据无脱敏方案 | §35.1 测试环境数据脱敏策略 |

### 一线运维视角：8 处不足

| # | 问题 | v2.0 现状 | v3.0 修正 |
|---|------|----------|----------|
| OP-1 | **无日常运维 SOP** | Runbook 仅故障场景 | 新增§37.1 日常运维操作手册（巡检/备份/清理/升级） |
| OP-2 | **无运维自动化脚本** | 运维操作全手工 | 新增§37.2 运维自动化脚本库（15 个常用脚本） |
| OP-3 | **无诊断排错工具集** | 故障排查无工具支持 | 新增§37.3 故障诊断工具包（one-liner 诊断命令） |
| OP-4 | **无版本升级标准流程** | 升级过程无 SOP | 新增§37.4 版本升级 SOP（含数据库兼容性检查） |
| OP-5 | **无证书/密钥轮换流程** | TLS 证书到期无预案 | 新增§37.5 证书与密钥轮换 SOP |
| OP-6 | **无依赖服务版本兼容矩阵** | MySQL/Redis 等版本兼容未定义 | 新增§37.6 依赖版本兼容矩阵 |
| OP-7 | **无运维值班告警升级** | 告警路由有但值班制度未设计 | 新增§37.7 值班轮换与告警升级制度 |
| OP-8 | **无容量规划 Review 机制** | 初始估算后无复审 | 新增§37.8 季度容量 Review 机制 |

---

## 目录

- [第一部分：战略概述](#第一部分战略概述)（同 v2.0）
- [第二部分：系统架构](#第二部分系统架构)（同 v2.0）
- [第三部分：详细设计](#第三部分详细设计)（同 v2.0）
- [第四部分：数据架构](#第四部分数据架构)（同 v2.0）
- [第五部分：安全与合规](#第五部分安全与合规)（同 v2.0）
- [第六部分：运维与保障](#第六部分运维与保障)（同 v2.0）
- [第七部分：实施规划](#第七部分实施规划)（同 v2.0）
- **[第八部分：部署工程化](#第八部分部署工程化)**（v3.0 新增）
- **[第九部分：CI/CD 管线](#第九部分cicd-管线)**（v3.0 新增）
- **[第十部分：可维护性设计](#第十部分可维护性设计)**（v3.0 新增）
- **[第十一部分：测试工程化](#第十一部分测试工程化)**（v3.0 新增）
- **[第十二部分：测试执行与度量](#第十二部分测试执行与度量)**（v3.0 新增）
- **[第十三部分：运维操作手册](#第十三部分运维操作手册)**（v3.0 新增）
- [附录](#附录)

---

# 第一部分～第七部分

> 同 v2.0，此处不赘述。以下为 v3.0 新增的第八～第十三部分。

---

# 第八部分：部署工程化

## 32. 基础设施即代码（IaC）

### 32.1 Helm Chart 设计 [v3.0 新增，修正 DO-1]

> **v2.0 不足：** 部署方案仅有零散 K8s YAML 片段，无统一打包、参数化、版本化能力。开发/运维无法一键部署。

```
项目仓库结构（部署相关）：

sia-deploy/                         ← 独立 GitOps 仓库
├── charts/
│   └── sia/                        ← 主 Helm Chart
│       ├── Chart.yaml              ← Chart 元数据 + 版本号
│       ├── values.yaml             ← 默认配置（生产基线）
│       ├── values-dev.yaml         ← 开发环境覆盖
│       ├── values-staging.yaml     ← 预发布环境覆盖
│       ├── values-prod.yaml        ← 生产环境覆盖（仅增量差异）
│       ├── templates/
│       │   ├── _helpers.tpl        ← 模板辅助函数
│       │   ├── namespace.yaml
│       │   ├── configmap.yaml      ← 统一配置
│       │   ├── secrets.yaml        ← Sealed Secrets 引用
│       │   ├── deployments/
│       │   │   ├── gateway.yaml
│       │   │   ├── collector.yaml
│       │   │   ├── analyzer.yaml
│       │   │   ├── reporter.yaml
│       │   │   ├── scheduler.yaml
│       │   │   └── web.yaml
│       │   ├── services/
│       │   │   └── *.yaml
│       │   ├── ingress.yaml
│       │   ├── hpa.yaml            ← HPA 自动伸缩
│       │   ├── networkpolicy.yaml  ← 网络策略
│       │   ├── cronjobs/
│       │   │   ├── data-cleanup.yaml
│       │   │   ├── backup.yaml
│       │   │   └── health-check.yaml
│       │   └── tests/
│       │       └── smoke-test.yaml ← Helm test hook
│       └── crds/                   ← 自定义资源定义（如有）
├── environments/
│   ├── dev/
│   │   └── kustomization.yaml     ← Kustomize 补丁（可选）
│   ├── staging/
│   │   └── kustomization.yaml
│   └── prod/
│       └── kustomization.yaml
├── Makefile                        ← 一键操作入口
└── scripts/
    ├── deploy.sh
    ├── rollback.sh
    ├── pre-deploy-check.sh
    └── post-deploy-smoke.sh
```

```yaml
# Chart.yaml
apiVersion: v2
name: sia
description: Security Intelligence Agent - Helm Chart
type: application
version: 0.1.0          # Chart 版本（部署配置变更时递增）
appVersion: "1.0.0"     # 应用版本（代码版本变更时递增）
dependencies:
  - name: mysql
    version: "9.x.x"
    repository: "https://charts.bitnami.com/bitnami"
    condition: mysql.enabled
  - name: redis
    version: "17.x.x"
    repository: "https://charts.bitnami.com/bitnami"
    condition: redis.enabled
  - name: milvus
    version: "4.x.x"
    repository: "https://milvus-io.github.io/milvus-helm"
    condition: milvus.enabled
  - name: minio
    version: "12.x.x"
    repository: "https://charts.bitnami.com/bitnami"
    condition: minio.enabled
```

```yaml
# values.yaml（默认生产配置基线，摘要）
global:
  imageRegistry: "harbor.internal.company.com/sia"
  imagePullPolicy: IfNotPresent
  storageClass: "ceph-ssd"

# ─── 应用服务 ───
gateway:
  replicas: 2
  image:
    tag: ""  # CI 自动填充
  resources:
    requests: { cpu: "500m", memory: "1Gi" }
    limits:   { cpu: "1",    memory: "2Gi" }
  env:
    LLM_ENDPOINT: "http://llm-gateway.llm-serving:8080"
    LLM_TIMEOUT: "60"
    LLM_RETRY_MAX: "3"
    CIRCUIT_BREAKER_THRESHOLD: "5"

collector:
  replicas: 2
  image:
    tag: ""
  resources:
    requests: { cpu: "1",   memory: "2Gi" }
    limits:   { cpu: "2",   memory: "4Gi" }
  env:
    COLLECT_CONCURRENCY: "10"
    COLLECT_TIMEOUT: "30"
    PROXY_URL: "http://squid-proxy.infra:3128"

analyzer:
  replicas: 2
  image:
    tag: ""
  resources:
    requests: { cpu: "2",   memory: "4Gi" }
    limits:   { cpu: "4",   memory: "8Gi" }

reporter:
  replicas: 1
  image:
    tag: ""
  resources:
    requests: { cpu: "1",   memory: "2Gi" }
    limits:   { cpu: "2",   memory: "4Gi" }

scheduler:
  replicas: 1
  image:
    tag: ""
  resources:
    requests: { cpu: "500m", memory: "1Gi" }
    limits:   { cpu: "1",    memory: "2Gi" }

web:
  replicas: 2
  image:
    tag: ""
  resources:
    requests: { cpu: "200m", memory: "256Mi" }
    limits:   { cpu: "500m", memory: "512Mi" }

# ─── 基础设施（通过 Bitnami subchart） ───
mysql:
  enabled: true
  primary:
    resources:
      requests: { cpu: "2", memory: "8Gi" }
    persistence:
      size: 200Gi
  secondary:
    replicaCount: 1

redis:
  enabled: true
  sentinel:
    enabled: true
  replica:
    replicaCount: 3

milvus:
  enabled: true
  standalone:
    resources:
      requests: { cpu: "2", memory: "8Gi" }

minio:
  enabled: true
  mode: distributed
  statefulset:
    replicaCount: 4

# ─── 可选组件 ───
elasticsearch:
  enabled: false   # Phase 3+ 启用
neo4j:
  enabled: false   # Phase 3+ 启用

# ─── 监控 ───
monitoring:
  prometheus:
    enabled: true
  grafana:
    enabled: true
    dashboards:
      enabled: true  # 自动导入 Dashboard JSON
  loki:
    enabled: true
```

```yaml
# values-dev.yaml（开发环境覆盖 — 仅列差异项）
global:
  imageRegistry: "localhost:5000"
  imagePullPolicy: Always
  storageClass: "local-path"

gateway:
  replicas: 1
  resources:
    requests: { cpu: "100m", memory: "256Mi" }
    limits:   { cpu: "500m", memory: "512Mi" }
  env:
    LLM_ENDPOINT: "http://llm-mock:8080"   # Mock LLM
    LOG_LEVEL: "DEBUG"

collector:
  replicas: 1
  resources:
    requests: { cpu: "100m", memory: "256Mi" }
    limits:   { cpu: "500m", memory: "1Gi" }
  env:
    COLLECT_CONCURRENCY: "2"

analyzer:
  replicas: 1
  resources:
    requests: { cpu: "200m", memory: "512Mi" }
    limits:   { cpu: "1",    memory: "2Gi" }

reporter:
  replicas: 1

scheduler:
  replicas: 1

web:
  replicas: 1

mysql:
  primary:
    resources:
      requests: { cpu: "200m", memory: "512Mi" }
    persistence:
      size: 5Gi
  secondary:
    replicaCount: 0  # 开发环境不需要从库

redis:
  sentinel:
    enabled: false   # 开发环境单节点
  replica:
    replicaCount: 1

milvus:
  standalone:
    resources:
      requests: { cpu: "200m", memory: "1Gi" }

minio:
  mode: standalone   # 开发环境单节点
  statefulset:
    replicaCount: 1
```

### 32.2 容器构建策略 [v3.0 新增，修正 DO-2, DO-10]

> **v2.0 不足：** 未定义 Dockerfile、镜像构建方式、镜像版本策略。

```dockerfile
# ─── 统一多阶段 Dockerfile（所有 Python 服务共用） ───
# sia-services/Dockerfile

# Stage 1: 依赖层（变化频率低，缓存友好）
FROM python:3.12-slim AS deps
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

# Stage 2: 应用层
FROM python:3.12-slim AS runtime
WORKDIR /app

# 安全加固：非 root 运行
RUN groupadd -r sia && useradd -r -g sia -d /app -s /sbin/nologin sia

# 复制依赖
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 复制应用代码
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# 复制运维脚本
COPY scripts/checkpoint-save.sh /app/
COPY scripts/healthcheck.py /app/

# 安全加固
RUN chown -R sia:sia /app && \
    chmod +x /app/checkpoint-save.sh
USER sia

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python /app/scripts/healthcheck.py

# 入口 — 通过环境变量 SIA_SERVICE 区分服务
ENV SIA_SERVICE="gateway"
ENTRYPOINT ["python", "-m", "src.main"]
```

```dockerfile
# ─── Web 前端 Dockerfile ───
# sia-web/Dockerfile

# Stage 1: 构建
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Stage 2: Nginx 运行
FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# 安全加固
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html
EXPOSE 80
```

**镜像 Tag 策略：**

```
镜像命名：harbor.internal.company.com/sia/<service>:<tag>

Tag 策略：
┌─────────────────┬────────────────────────────────┬───────────────┐
│ 触发场景         │ Tag 格式                        │ 示例           │
├─────────────────┼────────────────────────────────┼───────────────┤
│ 开发分支推送     │ dev-<branch>-<short-sha>       │ dev-feat-abc-a1b2c3d │
│ PR 合并到 main  │ main-<short-sha>               │ main-a1b2c3d  │
│ 正式发布         │ v<semver>                      │ v1.2.0        │
│ 热修复           │ v<semver>-hotfix.<n>           │ v1.2.0-hotfix.1 │
└─────────────────┴────────────────────────────────┴───────────────┘

镜像安全扫描：
  - 构建后自动运行 Trivy 扫描
  - HIGH/CRITICAL 漏洞 → 阻断推送到生产 Registry
  - 扫描报告附在 CI Pipeline Artifact
```

### 32.3 本地开发环境 [v3.0 新增，修正 DO-3]

> **v2.0 不足：** 开发者必须连接 K8s 集群才能开发调试。新成员上手门槛高，无法离线开发。

```yaml
# docker-compose.dev.yaml — 本地一键启动全栈开发环境
# 使用: make dev-up

services:
  # ─── 基础设施 ───
  mysql:
    image: mysql:8.0
    ports: ["3306:3306"]
    environment:
      MYSQL_ROOT_PASSWORD: dev_root_pass
      MYSQL_DATABASE: sia
    volumes:
      - mysql_data:/var/lib/mysql
      - ./db/init:/docker-entrypoint-initdb.d  # 自动执行初始 Schema
    healthcheck:
      test: mysqladmin ping -h localhost
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  milvus:
    image: milvusdb/milvus:v2.4-latest
    ports: ["19530:19530"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    depends_on: [etcd, minio-infra]

  etcd:
    image: quay.io/coreos/etcd:v3.5.11
    environment:
      ETCD_AUTO_COMPACTION_RETENTION: "1"
      ETCD_QUOTA_BACKEND_BYTES: "4294967296"
    command: etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls=http://0.0.0.0:2379

  minio-infra:
    image: minio/minio:latest
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

  # ─── LLM Mock Server（关键：开发/测试不依赖真实 LLM） ───
  llm-mock:
    build:
      context: ./tools/llm-mock
    ports: ["8090:8080"]
    volumes:
      - ./tools/llm-mock/responses:/app/responses  # 可编辑 Mock 响应
    environment:
      MOCK_MODE: "replay"        # replay=固定响应 / random=随机 / proxy=转发真实LLM
      MOCK_LATENCY_MS: "500"     # 模拟延迟

  # ─── 应用服务（可选：开发时通常直接本地跑 Python） ───
  # 取消注释以容器方式运行
  # gateway:
  #   build: { context: ., dockerfile: Dockerfile, target: runtime }
  #   environment:
  #     SIA_SERVICE: gateway
  #     MYSQL_HOST: mysql
  #     REDIS_HOST: redis
  #     LLM_ENDPOINT: http://llm-mock:8080
  #   ports: ["8080:8080"]
  #   depends_on: [mysql, redis, llm-mock]

  # ─── 可观测性（可选） ───
  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
    profiles: ["observability"]  # docker compose --profile observability up

volumes:
  mysql_data:
  redis_data:
  minio_data:
```

**本地开发快速上手：**

```
新成员上手流程（5 分钟启动）：

1. git clone ssh://git@gitlab.internal/sia/sia-services.git
2. cd sia-services
3. make dev-up                    # 启动基础设施 + LLM Mock
4. make db-migrate                # 执行数据库迁移
5. make dev-seed                  # 导入种子数据
6. make run service=gateway       # 本地启动 gateway 服务（热重载）

验证：
  curl http://localhost:8080/healthz       → {"status": "alive"}
  curl http://localhost:8080/readyz        → {"status": "ready", ...}
  curl http://localhost:8090/v1/chat       → LLM Mock 响应

清理：
  make dev-down                   # 停止并清理容器
  make dev-clean                  # 清理容器 + 数据卷
```

### 32.4 环境管理策略 [v3.0 新增，修正 DO-5]

> **v2.0 不足：** 未区分 dev/staging/prod 环境，配置管理无分层策略。

```
三环境分层策略：

┌──────────┬─────────────────────┬──────────────────────┬──────────────────────┐
│ 维度      │ Dev                  │ Staging              │ Prod                 │
├──────────┼─────────────────────┼──────────────────────┼──────────────────────┤
│ 用途      │ 开发调试              │ 集成测试/预发布        │ 正式生产              │
│ K8s      │ 本地/共享开发集群      │ 独立 Namespace        │ 独立集群              │
│ 数据      │ 种子数据 + Mock       │ 脱敏生产数据子集       │ 真实数据              │
│ LLM      │ LLM Mock Server      │ 真实 LLM（限流）      │ 真实 LLM              │
│ 外部推送  │ 控制台日志（不真推）    │ 测试企微群/邮箱       │ 真实渠道              │
│ 外部采集  │ Mock RSS/本地文件     │ 真实源（限量 10 个）   │ 真实源（全量）         │
│ 副本数    │ 各 1                  │ 各 1                  │ 按 values.yaml       │
│ 资源      │ 最小化                │ 生产 1/4              │ 完整配置              │
│ 部署方式  │ make dev-up          │ ArgoCD 自动同步       │ ArgoCD + 审批         │
│ 数据库    │ SQLite 可选/MySQL     │ MySQL 单节点          │ MySQL 主从            │
│ 谁可访问  │ 开发者                │ 开发 + 测试           │ 运维 + 审批后         │
│ 日志级别  │ DEBUG                │ INFO                  │ INFO (可临时 DEBUG)   │
└──────────┴─────────────────────┴──────────────────────┴──────────────────────┘

环境配置覆盖链：
  values.yaml (基线) → values-{env}.yaml (环境差异) → Sealed Secrets (敏感值)

原则：
  - 配置差异最小化：仅覆盖必须不同的值
  - staging 尽可能接近 prod（发现配置问题）
  - dev 尽可能轻量（降低开发门槛）
  - 敏感配置永不出现在 values 文件中
```

### 32.5 一键部署脚本 [v3.0 新增，修正 DO-9]

```makefile
# Makefile — 开发/部署/运维操作统一入口

# ─── 变量 ───
ENV        ?= dev
CHART_DIR  := charts/sia
IMAGE_TAG  ?= $(shell git rev-parse --short HEAD)
REGISTRY   ?= harbor.internal.company.com/sia
NAMESPACE  ?= sia-$(ENV)

# ─── 本地开发 ───
.PHONY: dev-up dev-down dev-clean dev-seed

dev-up:                     ## 启动本地开发环境
	docker compose -f docker-compose.dev.yaml up -d
	@echo "等待 MySQL 就绪..."
	@until docker compose -f docker-compose.dev.yaml exec mysql mysqladmin ping -h localhost --silent; do sleep 1; done
	@echo "✓ 基础设施就绪。LLM Mock: http://localhost:8090"

dev-down:                   ## 停止本地开发环境
	docker compose -f docker-compose.dev.yaml down

dev-clean:                  ## 清理本地环境（含数据卷）
	docker compose -f docker-compose.dev.yaml down -v

dev-seed:                   ## 导入种子数据
	python -m src.scripts.seed_data --env dev

# ─── 数据库迁移 ───
.PHONY: db-migrate db-rollback db-status

db-migrate:                 ## 执行数据库迁移到最新版本
	alembic upgrade head

db-rollback:                ## 回退上一次数据库迁移
	alembic downgrade -1

db-status:                  ## 查看当前数据库迁移状态
	alembic current

db-history:                 ## 查看迁移历史
	alembic history --verbose

# ─── 构建 ───
.PHONY: build build-all push

build:                      ## 构建单个服务镜像 (make build service=gateway)
	docker build -t $(REGISTRY)/sia-$(service):$(IMAGE_TAG) \
	  --build-arg SIA_SERVICE=$(service) .

build-all:                  ## 构建所有服务镜像
	@for svc in gateway collector analyzer reporter scheduler web; do \
	  echo "Building $$svc..."; \
	  $(MAKE) build service=$$svc; \
	done

push:                       ## 推送镜像到 Registry
	@for svc in gateway collector analyzer reporter scheduler web; do \
	  docker push $(REGISTRY)/sia-$$svc:$(IMAGE_TAG); \
	done

# ─── 部署 ───
.PHONY: deploy deploy-dry rollback

deploy-dry:                 ## 预览部署变更（dry-run）
	helm diff upgrade sia $(CHART_DIR) \
	  -f $(CHART_DIR)/values-$(ENV).yaml \
	  --namespace $(NAMESPACE) \
	  --set global.imageTag=$(IMAGE_TAG)

deploy:                     ## 部署到指定环境 (make deploy ENV=staging)
	@$(MAKE) pre-deploy-check
	helm upgrade --install sia $(CHART_DIR) \
	  -f $(CHART_DIR)/values-$(ENV).yaml \
	  --namespace $(NAMESPACE) --create-namespace \
	  --set global.imageTag=$(IMAGE_TAG) \
	  --wait --timeout 10m
	@$(MAKE) smoke-test

rollback:                   ## 回滚到上一版本
	helm rollback sia --namespace $(NAMESPACE) --wait

pre-deploy-check:           ## 部署前置检查
	@./scripts/pre-deploy-check.sh $(ENV)

# ─── 测试 ───
.PHONY: test test-unit test-integration test-e2e smoke-test lint

test:                       ## 运行所有测试
	$(MAKE) test-unit test-integration

test-unit:                  ## 单元测试
	pytest tests/unit/ -v --cov=src --cov-report=term-missing

test-integration:           ## 集成测试（需要 docker compose 环境）
	pytest tests/integration/ -v --timeout=60

test-e2e:                   ## 端到端测试（需要完整环境）
	pytest tests/e2e/ -v --timeout=300

smoke-test:                 ## 部署后冒烟测试
	@./scripts/post-deploy-smoke.sh $(ENV)

lint:                       ## 代码质量检查
	ruff check src/ tests/
	ruff format --check src/ tests/
	helm lint $(CHART_DIR) -f $(CHART_DIR)/values-$(ENV).yaml

# ─── 运维 ───
.PHONY: logs status diagnose

status:                     ## 查看部署状态
	kubectl get pods -n $(NAMESPACE) -o wide
	kubectl get svc -n $(NAMESPACE)

logs:                       ## 查看服务日志 (make logs service=collector)
	kubectl logs -n $(NAMESPACE) -l app=sia-$(service) --tail=100 -f

diagnose:                   ## 运行诊断检查
	@./scripts/diagnose.sh $(NAMESPACE)

# ─── 本地服务运行（热重载） ───
.PHONY: run

run:                        ## 本地运行服务 (make run service=gateway)
	SIA_SERVICE=$(service) \
	MYSQL_HOST=localhost \
	REDIS_HOST=localhost \
	LLM_ENDPOINT=http://localhost:8090 \
	LOG_LEVEL=DEBUG \
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# ─── 帮助 ───
.PHONY: help
help:                       ## 显示此帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
```

### 32.6 服务依赖启动顺序 [v3.0 新增，修正 DO-14]

> **v2.0 不足：** 多个服务同时启动，可能在依赖服务未就绪时崩溃重启。

```yaml
# Helm template 中的 initContainers 设计

# ─── sia-collector 的依赖等待 ───
initContainers:
  - name: wait-mysql
    image: busybox:1.36
    command: ['sh', '-c',
      'until nc -z {{ .Release.Name }}-mysql {{ .Values.mysql.port | default 3306 }};
       do echo "等待 MySQL..."; sleep 2; done']
  - name: wait-redis
    image: busybox:1.36
    command: ['sh', '-c',
      'until nc -z {{ .Release.Name }}-redis-master {{ .Values.redis.port | default 6379 }};
       do echo "等待 Redis..."; sleep 2; done']
  - name: db-migrate
    image: "{{ .Values.global.imageRegistry }}/sia-collector:{{ .Values.collector.image.tag }}"
    command: ['alembic', 'upgrade', 'head']
    env:
      {{- include "sia.dbEnv" . | nindent 6 }}

# ─── 依赖关系矩阵 ───
#
# 服务            │ 依赖                │ initContainers 等待
# ─────────────── │ ────────────────── │ ─────────────────────
# sia-gateway     │ LLM, Redis         │ wait-redis
# sia-collector   │ MySQL, Redis,      │ wait-mysql, wait-redis, db-migrate
#                 │ Milvus             │ wait-milvus
# sia-analyzer    │ MySQL, Redis,      │ wait-mysql, wait-redis, wait-milvus
#                 │ Milvus, Gateway    │
# sia-reporter    │ MySQL, Redis,      │ wait-mysql, wait-redis, wait-minio
#                 │ MinIO, Gateway     │
# sia-scheduler   │ MySQL, Redis       │ wait-mysql, wait-redis
# sia-web         │ Gateway            │ (无 — 前端通过 API 调用)
#
# db-migrate 仅在 sia-collector 中执行（避免多服务并发迁移）
# 其他服务通过 readinessProbe 等待 sia-collector 完成迁移
```

---

## 33. CI/CD 管线 [v3.0 新增，修正 DO-4]

### 33.1 管线总览

```
CI/CD Pipeline 全景图：

   代码推送
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│  CI 阶段（每次 Push / MR）                                       │
│                                                                 │
│  ① Lint & Format Check                                         │
│     ├─ ruff check + ruff format --check                        │
│     ├─ helm lint                                                │
│     ├─ hadolint (Dockerfile)                                    │
│     └─ shellcheck (scripts/)                                    │
│                                                                 │
│  ② 单元测试                                                     │
│     ├─ pytest tests/unit/ --cov                                │
│     ├─ 覆盖率 Gate: ≥ 80%                                      │
│     └─ 生成 JUnit XML + 覆盖率报告                               │
│                                                                 │
│  ③ 集成测试                                                     │
│     ├─ docker compose -f docker-compose.test.yaml up            │
│     ├─ pytest tests/integration/                                │
│     └─ 清理测试容器                                              │
│                                                                 │
│  ④ 构建镜像                                                     │
│     ├─ docker build (多阶段)                                    │
│     └─ Trivy 安全扫描 (CRITICAL → 阻断)                         │
│                                                                 │
│  ⑤ 推送镜像（仅 main 分支 / tag）                                │
│     └─ harbor.internal.company.com/sia/<service>:<tag>          │
│                                                                 │
│  ⑥ Prompt 回归测试（仅涉及 Prompt 变更时）                       │
│     ├─ 在黄金标注集上评估                                        │
│     └─ 分类准确率 ≥ 85% AND 评分 ρ ≥ 0.80 → PASS               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼ (main 分支合并后自动)
┌─────────────────────────────────────────────────────────────────┐
│  CD 阶段                                                        │
│                                                                 │
│  ⑦ 自动部署到 Staging                                           │
│     └─ ArgoCD 同步 staging 环境                                 │
│                                                                 │
│  ⑧ Staging 冒烟测试（自动）                                     │
│     ├─ 健康检查 /healthz /readyz                                │
│     ├─ 核心 API 可用性验证                                      │
│     └─ 端到端流程验证（Mock 数据）                                │
│                                                                 │
│  ⑨ 部署到 Prod（需审批）                                        │
│     ├─ MR 审批 + 运维确认                                       │
│     ├─ ArgoCD 同步 prod 环境                                    │
│     └─ Prod 冒烟测试                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 33.2 GitLab CI 配置

```yaml
# .gitlab-ci.yml
stages:
  - lint
  - test
  - build
  - scan
  - deploy-staging
  - smoke-staging
  - deploy-prod

variables:
  REGISTRY: harbor.internal.company.com/sia
  IMAGE_TAG: ${CI_COMMIT_SHORT_SHA}

# ─── Lint ───
lint:
  stage: lint
  image: python:3.12-slim
  script:
    - pip install ruff
    - ruff check src/ tests/
    - ruff format --check src/ tests/
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

helm-lint:
  stage: lint
  image: alpine/helm:3.14
  script:
    - helm lint charts/sia -f charts/sia/values-dev.yaml
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - charts/**/*

# ─── 单元测试 ───
unit-test:
  stage: test
  image: python:3.12-slim
  script:
    - pip install uv && uv sync --frozen
    - pytest tests/unit/ -v
      --cov=src
      --cov-report=xml:coverage.xml
      --cov-report=term-missing
      --junitxml=report.xml
      --cov-fail-under=80
  artifacts:
    reports:
      junit: report.xml
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

# ─── 集成测试 ───
integration-test:
  stage: test
  image: python:3.12-slim
  services:
    - mysql:8.0
    - redis:7-alpine
  variables:
    MYSQL_ROOT_PASSWORD: test
    MYSQL_DATABASE: sia_test
    REDIS_HOST: redis
  script:
    - pip install uv && uv sync --frozen
    - alembic upgrade head
    - pytest tests/integration/ -v --timeout=60 --junitxml=integration-report.xml
  artifacts:
    reports:
      junit: integration-report.xml

# ─── 构建 ───
build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - |
      for svc in gateway collector analyzer reporter scheduler; do
        docker build -t ${REGISTRY}/sia-${svc}:${IMAGE_TAG} \
          --build-arg SIA_SERVICE=${svc} .
      done
    - docker build -t ${REGISTRY}/sia-web:${IMAGE_TAG} -f sia-web/Dockerfile sia-web/
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# ─── 安全扫描 ───
trivy-scan:
  stage: scan
  image: aquasec/trivy:latest
  script:
    - |
      for svc in gateway collector analyzer reporter scheduler web; do
        trivy image --severity HIGH,CRITICAL --exit-code 1 \
          ${REGISTRY}/sia-${svc}:${IMAGE_TAG}
      done
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  allow_failure: false

# ─── 部署 Staging ───
deploy-staging:
  stage: deploy-staging
  image: alpine/helm:3.14
  script:
    - helm upgrade --install sia charts/sia
        -f charts/sia/values-staging.yaml
        --namespace sia-staging --create-namespace
        --set global.imageTag=${IMAGE_TAG}
        --wait --timeout 10m
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# ─── Staging 冒烟测试 ───
smoke-staging:
  stage: smoke-staging
  image: curlimages/curl:latest
  script:
    - ./scripts/post-deploy-smoke.sh staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# ─── 部署 Prod（手动审批） ───
deploy-prod:
  stage: deploy-prod
  image: alpine/helm:3.14
  script:
    - helm upgrade --install sia charts/sia
        -f charts/sia/values-prod.yaml
        --namespace sia-prod
        --set global.imageTag=${IMAGE_TAG}
        --wait --timeout 10m
    - ./scripts/post-deploy-smoke.sh prod
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: manual  # 手动触发 + 审批
```

### 33.3 部署前置检查清单 [v3.0 新增，修正 DO-12]

```bash
#!/bin/bash
# scripts/pre-deploy-check.sh — 部署前自动化检查
set -euo pipefail

ENV=${1:-staging}
echo "===== SIA Pre-Deploy Checks (ENV=${ENV}) ====="

FAILED=0

# Check 1: Helm Chart 语法
echo -n "[1/8] Helm Lint... "
if helm lint charts/sia -f "charts/sia/values-${ENV}.yaml" > /dev/null 2>&1; then
    echo "PASS"
else
    echo "FAIL"; FAILED=1
fi

# Check 2: K8s 集群连通性
echo -n "[2/8] K8s Cluster... "
if kubectl cluster-info > /dev/null 2>&1; then
    echo "PASS"
else
    echo "FAIL - 无法连接 K8s 集群"; FAILED=1
fi

# Check 3: 镜像存在性
echo -n "[3/8] Image Exists... "
IMAGE_TAG=${IMAGE_TAG:-$(git rev-parse --short HEAD)}
for svc in gateway collector analyzer reporter scheduler web; do
    if ! docker manifest inspect "${REGISTRY}/sia-${svc}:${IMAGE_TAG}" > /dev/null 2>&1; then
        echo "FAIL - sia-${svc}:${IMAGE_TAG} 不存在"; FAILED=1
    fi
done
[ $FAILED -eq 0 ] && echo "PASS"

# Check 4: 数据库迁移兼容性
echo -n "[4/8] DB Migration... "
CURRENT=$(alembic current 2>/dev/null | head -1)
HEAD=$(alembic heads 2>/dev/null | head -1)
if [ "$CURRENT" == "$HEAD" ]; then
    echo "PASS (already at head)"
else
    echo "WARN - 待执行迁移: ${CURRENT} → ${HEAD}"
fi

# Check 5: Secrets 是否配置
echo -n "[5/8] Secrets... "
NS="sia-${ENV}"
REQUIRED_SECRETS="sia-db-credentials sia-redis-credentials sia-llm-api-key"
for secret in $REQUIRED_SECRETS; do
    if ! kubectl get secret "$secret" -n "$NS" > /dev/null 2>&1; then
        echo "FAIL - Secret ${secret} 不存在"; FAILED=1
    fi
done
[ $FAILED -eq 0 ] && echo "PASS"

# Check 6: 磁盘空间
echo -n "[6/8] Disk Space... "
USAGE=$(kubectl exec -n "$NS" deploy/sia-mysql-primary -- \
    df /var/lib/mysql --output=pcent 2>/dev/null | tail -1 | tr -d '% ')
if [ "${USAGE:-0}" -gt 80 ]; then
    echo "WARN - MySQL 磁盘使用 ${USAGE}%"
else
    echo "PASS (${USAGE:-?}%)"
fi

# Check 7: 当前环境健康状态
echo -n "[7/8] Current Health... "
UNHEALTHY=$(kubectl get pods -n "$NS" --no-headers 2>/dev/null | \
    grep -v Running | grep -v Completed | wc -l)
if [ "$UNHEALTHY" -gt 0 ]; then
    echo "WARN - ${UNHEALTHY} 个 Pod 异常"
else
    echo "PASS"
fi

# Check 8: 待处理告警
echo -n "[8/8] Active Alerts... "
ALERTS=$(curl -s "http://alertmanager.sia-monitor:9093/api/v2/alerts?silenced=false&active=true" | \
    python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
if [ "$ALERTS" != "0" ] && [ "$ALERTS" != "?" ]; then
    echo "WARN - ${ALERTS} 个活跃告警"
else
    echo "PASS"
fi

echo ""
if [ $FAILED -gt 0 ]; then
    echo "❌ 前置检查失败，请修复后重试"
    exit 1
else
    echo "✅ 所有前置检查通过"
fi
```

### 33.4 ArgoCD GitOps 工作流 [v3.0 新增，修正 DO-8]

```
ArgoCD GitOps 部署流程：

┌────────────┐     ┌────────────┐     ┌────────────┐
│ sia-services│     │ sia-deploy │     │ ArgoCD     │
│ (代码仓库)  │     │ (部署仓库) │     │ (部署引擎)  │
└─────┬──────┘     └─────┬──────┘     └─────┬──────┘
      │                  │                  │
      │ 1. Push代码      │                  │
      │ 2. CI Pipeline   │                  │
      │ 3. 构建+推送镜像  │                  │
      │                  │                  │
      │ 4. CI 更新       │                  │
      │ image tag ──────►│                  │
      │ (自动 commit)    │                  │
      │                  │ 5. Git webhook   │
      │                  │ ───────────────► │
      │                  │                  │ 6. Detect diff
      │                  │                  │ 7. Sync K8s
      │                  │                  │
      │                  │     staging:     │
      │                  │     自动同步     │
      │                  │                  │
      │                  │     prod:        │
      │                  │     手动同步     │
      │                  │     (需审批)     │

ArgoCD Application 配置：
```

```yaml
# ArgoCD Application - Staging
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sia-staging
  namespace: argocd
spec:
  project: sia
  source:
    repoURL: ssh://git@gitlab.internal/sia/sia-deploy.git
    targetRevision: main
    path: charts/sia
    helm:
      valueFiles:
        - values.yaml
        - values-staging.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: sia-staging
  syncPolicy:
    automated:           # staging 自动同步
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
    retry:
      limit: 3
      backoff:
        duration: 5s
        maxDuration: 3m
```

```yaml
# ArgoCD Application - Prod (手动同步)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: sia-prod
  namespace: argocd
spec:
  project: sia
  source:
    repoURL: ssh://git@gitlab.internal/sia/sia-deploy.git
    targetRevision: main
    path: charts/sia
    helm:
      valueFiles:
        - values.yaml
        - values-prod.yaml
  destination:
    server: https://k8s-prod.internal:6443
    namespace: sia-prod
  syncPolicy:
    # 无 automated — 需要手动在 ArgoCD UI 点击 Sync
    syncOptions:
      - CreateNamespace=true
```

---

# 第十部分：可维护性设计

## 34. 运维基础设施

### 34.1 数据库迁移管理 [v3.0 新增，修正 DO-6]

> **v2.0 不足：** 数据库 Schema 直接给 DDL 文件，无版本管理。线上 Schema 变更风险高，无法回退。

```
数据库迁移方案：Alembic + SQLAlchemy

项目结构：
sia-services/
├── alembic/
│   ├── env.py               ← Alembic 环境配置
│   ├── versions/             ← 迁移脚本（自动生成 + 手动审核）
│   │   ├── 001_initial_schema.py
│   │   ├── 002_add_ioc_indicators.py
│   │   ├── 003_add_outbox_table.py
│   │   ├── 004_add_subscriber_preferences.py
│   │   └── ...
│   └── script.py.mako        ← 迁移脚本模板
├── alembic.ini               ← Alembic 配置
└── src/models/               ← SQLAlchemy ORM 模型
    ├── __init__.py
    ├── intelligence.py
    ├── report.py
    ├── source.py
    ├── subscriber.py
    └── audit.py

迁移工作流：
  1. 修改 ORM 模型
  2. alembic revision --autogenerate -m "描述"  ← 自动生成迁移
  3. 人工审核迁移脚本（必须！autogenerate 不总是正确）
  4. alembic upgrade head  ← 本地测试
  5. 提交代码 → CI 中自动执行迁移

安全规则：
  - 迁移脚本一旦推送到 main 分支，禁止修改
  - 需要修正 → 创建新的迁移脚本
  - 高风险迁移（大表 ALTER）需要 DBA 审核
  - 生产环境迁移前先在 staging 执行验证
  - 所有迁移必须可回退（downgrade 方法必须实现）
```

```python
# alembic/versions/001_initial_schema.py — 迁移脚本示例

"""Initial schema - 核心表结构

Revision ID: 001
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None

def upgrade() -> None:
    # 情报源表
    op.create_table('intel_sources',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('source_type', sa.Enum('rss', 'wechat', 'web', 'api', 'darkweb',
                                          'social', 'regulation')),
        sa.Column('url', sa.String(2000)),
        sa.Column('status', sa.Enum('active', 'inactive', 'error'), default='active'),
        sa.Column('language', sa.String(10), default='zh'),
        sa.Column('region', sa.Enum('cn', 'global', 'eu', 'sea')),
        sa.Column('collect_frequency', sa.Integer(), default=3600),
        sa.Column('last_collected_at', sa.DateTime()),
        sa.Column('error_count', sa.Integer(), default=0),
        sa.Column('config', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()')),
    )
    # ... 其他表
    # 完整 DDL 参见 v2.0 §19 数据模型

def downgrade() -> None:
    op.drop_table('intel_sources')
    # ... 其他表
```

### 34.2 Secrets 管理 [v3.0 新增，修正 DO-7]

> **v2.0 不足：** 仅说"用环境变量"，未设计 Secret 存储、轮换和分发机制。

```
Secrets 管理方案：K8s Sealed Secrets（推荐）

方案选型理由：
  ┌─────────────────┬────────────────────┬────────────────────┐
  │ 方案             │ 优点                │ 缺点                │
  ├─────────────────┼────────────────────┼────────────────────┤
  │ Sealed Secrets  │ 轻量，可入 Git，     │ 无动态轮换           │
  │ (推荐)          │ 无额外组件，学习     │                     │
  │                 │ 成本低              │                     │
  ├─────────────────┼────────────────────┼────────────────────┤
  │ Vault           │ 功能强大，动态       │ 重：需独立部署运维    │
  │ (大规模)        │ Secret，审计完善     │ 学习曲线陡           │
  ├─────────────────┼────────────────────┼────────────────────┤
  │ SOPS            │ 可入 Git，支持多     │ 密钥管理依赖 KMS     │
  │                 │ KMS 后端            │                     │
  └─────────────────┴────────────────────┴────────────────────┘

Sealed Secrets 工作流：

  1. 安装 Sealed Secrets Controller（集群中）
  2. 在本地创建 Secret YAML（明文）
  3. 用 kubeseal 加密 → 生成 SealedSecret YAML
  4. SealedSecret YAML 安全入 Git
  5. Controller 在集群中解密为普通 Secret

  明文 Secret ──kubeseal──→ SealedSecret (入 Git) ──Controller──→ K8s Secret

Secret 清单：
  ┌─────────────────────┬────────────────────────────┐
  │ Secret Name          │ 内容                        │
  ├─────────────────────┼────────────────────────────┤
  │ sia-db-credentials   │ MYSQL_USER, MYSQL_PASSWORD │
  │ sia-redis-credentials│ REDIS_PASSWORD             │
  │ sia-llm-api-key      │ LLM_API_KEY                │
  │ sia-wechat-webhook   │ WECHAT_WEBHOOK_URL         │
  │ sia-feishu-webhook   │ FEISHU_WEBHOOK_URL         │
  │ sia-smtp-credentials │ SMTP_USER, SMTP_PASSWORD   │
  │ sia-minio-credentials│ MINIO_ACCESS_KEY,          │
  │                      │ MINIO_SECRET_KEY           │
  │ sia-sms-api-key      │ SMS_API_KEY                │
  └─────────────────────┴────────────────────────────┘

轮换策略：
  - 数据库密码：每 90 天轮换
  - API Key：每 180 天轮换
  - TLS 证书：90 天前自动告警（cert-manager）
  - 轮换脚本：make rotate-secret name=sia-db-credentials
```

### 34.3 一键回滚 SOP [v3.0 新增，修正 DO-13]

> **v2.0 不足：** 仅提到"回滚 canary"，无完整回滚标准流程。

```
回滚 SOP（Standard Operating Procedure）：

场景 A: 应用代码回滚（无数据库变更）
───────────────────────────────────
  1. 确认回滚目标版本
     $ helm history sia -n sia-prod
     REVISION  UPDATED       STATUS      DESCRIPTION
     5         2026-03-28    superseded  v1.2.0
     6         2026-03-29    deployed    v1.3.0  ← 当前

  2. 执行回滚
     $ helm rollback sia 5 -n sia-prod --wait
     或
     $ make rollback ENV=prod

  3. 验证回滚
     $ make smoke-test ENV=prod

  4. 记录事件
     在运维事件日志中记录回滚原因和时间

场景 B: 应用代码回滚（含数据库变更）
───────────────────────────────────
  ⚠️ 需要额外处理数据库兼容性

  前提：数据库迁移设计遵循"向前兼容"原则
    - 新增列 → 设默认值（旧代码忽略新列，不报错）
    - 删除列 → 先部署不使用该列的代码，再删列（两步走）
    - 改列名 → 禁止。新增列 + 数据迁移 + 删旧列（三步走）

  回滚步骤：
  1. 确认当前迁移版本
     $ alembic current

  2. 评估是否需要数据库回退
     - 如果迁移仅是 ADD COLUMN → 不需要回退（旧代码兼容）
     - 如果迁移是 DROP COLUMN → 必须先回退数据库

  3. 如需数据库回退：
     $ alembic downgrade -1
     确认数据完整性

  4. 回滚应用
     $ helm rollback sia <revision> -n sia-prod --wait

  5. 验证
     $ make smoke-test ENV=prod

场景 C: Prompt/模型回滚
───────────────────────
  1. 在 Dify 界面切换到上一版本 Workflow
  2. 或修改 ConfigMap 中的 Prompt 版本号
  3. 重启 sia-analyzer Pod（自动加载新配置）
     $ kubectl rollout restart deploy/sia-analyzer -n sia-prod
```

### 34.4 Grafana Dashboard 即代码 [v3.0 新增，修正 DO-15]

> **v2.0 不足：** 提到 Grafana Dashboard 名称但无模板，Dashboard 手动创建后无法版本化。

```
Dashboard 即代码方案：
  - Dashboard JSON 文件存放在 Git 仓库
  - 通过 Grafana Provisioning 自动导入
  - 修改 Dashboard → 导出 JSON → 提交 Git → 自动同步

目录结构：
  monitoring/grafana/
  ├── provisioning/
  │   ├── dashboards/
  │   │   └── default.yaml          ← Dashboard provider 配置
  │   └── datasources/
  │       └── default.yaml          ← Prometheus/Loki 数据源
  └── dashboards/
      ├── sia-business.json         ← 业务指标仪表盘
      ├── sia-system.json           ← 系统指标仪表盘
      ├── sia-infra.json            ← 基础设施仪表盘
      ├── sia-llm.json              ← LLM 调用监控
      ├── sia-pipeline.json         ← 情报处理管线
      └── sia-test-quality.json     ← 测试质量仪表盘

Dashboard 清单与核心 Panel：
  ┌──────────────────┬────────────────────────────────────────────┐
  │ Dashboard         │ 核心 Panel                                  │
  ├──────────────────┼────────────────────────────────────────────┤
  │ SIA-Business     │ 每日采集量趋势、去重率、P0/P1 计数、         │
  │                  │ 日报推送时间、情报源健康率、反馈满意度         │
  ├──────────────────┼────────────────────────────────────────────┤
  │ SIA-System       │ LLM 延迟分布、LLM 错误率、Token 消耗、       │
  │                  │ Redis Stream 积压、DB 连接池使用率            │
  ├──────────────────┼────────────────────────────────────────────┤
  │ SIA-Infra        │ CPU/Memory 使用率（按 Pod）、PV 使用率、      │
  │                  │ 网络 I/O、Pod 重启次数                       │
  ├──────────────────┼────────────────────────────────────────────┤
  │ SIA-LLM          │ 模型调用分布、评分分布、Schema 校验通过率、   │
  │                  │ 熔断器状态、降级次数                          │
  ├──────────────────┼────────────────────────────────────────────┤
  │ SIA-Pipeline     │ 管线各阶段耗时、DLQ 消息数、Outbox 积压、     │
  │                  │ 数据质量门控通过率                             │
  └──────────────────┴────────────────────────────────────────────┘
```

### 34.5 日志采集管线 [v3.0 新增，修正 DO-16]

```
日志采集管线设计：

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 应用容器      │    │ Promtail     │    │ Loki         │
│ stdout/stderr │──►│ (DaemonSet)  │──►│ (日志存储)    │
│ JSON 格式    │    │ 自动发现 Pod  │    │ 支持 LogQL   │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                                │
                                        ┌───────▼───────┐
                                        │ Grafana       │
                                        │ Explore       │
                                        │ (日志查询UI)   │
                                        └───────────────┘

标签设计（Label）：
  - namespace: sia-system / sia-staging
  - app: sia-gateway / sia-collector / ...
  - pod: sia-collector-xxx-yyy
  - container: main / init-wait-mysql
  - level: ERROR / WARN / INFO / DEBUG

常用查询（LogQL）：
  # 查看某服务错误日志
  {app="sia-collector"} |= "ERROR"

  # 按 trace_id 追踪单条情报处理链路
  {namespace="sia-prod"} | json | trace_id="abc-123-def"

  # 统计每小时错误数
  sum(count_over_time({app="sia-analyzer"} |= "ERROR" [1h])) by (app)

日志保留策略：
  - 生产：30 天
  - 预发：7 天
  - 开发：3 天
  - ERROR 级别：90 天（单独保留规则）
```

---

# 第十一部分：测试工程化

## 35. 测试基础设施

### 35.1 测试环境架构 [v3.0 新增，修正 TE-1, TE-18]

> **v2.0 不足：** 未设计隔离的测试环境，测试可能影响其他环境数据。

```
测试环境分层架构：

┌─────────────────────────────────────────────────────────────────┐
│ Level 1: 单元测试环境（本地 / CI）                                │
│                                                                 │
│  • 无外部依赖                                                    │
│  • 所有外部服务通过 Mock/Stub 替代                                │
│  • SQLite 内存数据库（或 fakeredis）                              │
│  • 执行时间：< 2 分钟                                            │
│  • 触发：每次 git push                                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Level 2: 集成测试环境（CI + Testcontainers）                      │
│                                                                 │
│  • Testcontainers 启动真实 MySQL + Redis + Milvus                │
│  • LLM 使用 Mock Server（确定性输出）                             │
│  • 外部 API（企微/飞书/NVD）使用 Mock Server                     │
│  • 每次测试自动创建/销毁容器                                      │
│  • 测试数据通过 TestDataFactory 生成                              │
│  • 执行时间：< 10 分钟                                           │
│  • 触发：每次 MR / 每日 CI                                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Level 3: E2E 测试环境（Staging 命名空间）                         │
│                                                                 │
│  • 完整 K8s 部署（与 Prod 同构，资源缩减）                        │
│  • 真实 LLM（限流模式）                                          │
│  • 推送渠道：测试企微群 / 测试邮箱                                 │
│  • 采集源：10 个真实源 + Mock 源                                  │
│  • 执行时间：< 30 分钟                                           │
│  • 触发：部署到 staging 后自动 / 每周定时                         │
└─────────────────────────────────────────────────────────────────┘

测试数据脱敏策略（TE-18）：
  - 生产数据导入 staging/dev 前必须脱敏
  - 脱敏规则：
    ┌──────────────┬──────────────────────────────┐
    │ 字段类型      │ 脱敏方式                       │
    ├──────────────┼──────────────────────────────┤
    │ 人名          │ 替换为 Faker 生成的假名         │
    │ 邮箱          │ user@example.com              │
    │ 手机号        │ 138****1234                   │
    │ IP 地址       │ 保留前两段，后两段随机           │
    │ 企业内部 URL  │ 替换为 internal.example.com     │
    │ API Key       │ 全部替换为 test-key-xxx         │
    │ 情报正文      │ 保留（非个人敏感数据）           │
    └──────────────┴──────────────────────────────┘
  - 脱敏脚本：make data-sanitize source=prod target=staging
```

### 35.2 外部依赖 Mock 策略 [v3.0 新增，修正 TE-2, TE-14]

> **v2.0 不足：** 测试如何 Mock LLM、企微、飞书、NVD 等外部依赖完全未定义。测试必须依赖真实外部服务，不可控且不稳定。

```
Mock 策略总览：

┌──────────────┬─────────────────────────────────┬───────────────────┐
│ 外部依赖      │ Mock 方案                         │ 使用场景           │
├──────────────┼─────────────────────────────────┼───────────────────┤
│ LLM 服务      │ LLM Mock Server（专用）           │ 单元/集成/E2E     │
│ 企微 API      │ WireMock / 自定义 Mock Server    │ 集成/E2E          │
│ 飞书 API      │ WireMock / 自定义 Mock Server    │ 集成/E2E          │
│ SMTP 邮件     │ MailHog (本地邮件服务器)          │ 集成/E2E          │
│ NVD/CNVD API │ 本地 JSON 文件 + Mock Server     │ 集成              │
│ RSS Feed     │ 本地 XML 文件 + HTTP Server      │ 集成/E2E          │
│ 暗网/Tor      │ Mock HTTP Server                │ 集成              │
│ EPSS API     │ 本地 JSON 文件                    │ 集成              │
│ 短信 API      │ 日志 Mock（记录发送内容不真发）    │ 集成/E2E          │
└──────────────┴─────────────────────────────────┴───────────────────┘
```

**LLM Mock Server（核心组件）：**

```python
# tools/llm-mock/server.py — LLM Mock Server
"""
SIA LLM Mock Server
支持三种模式：
  - replay:  根据输入关键词匹配预定义响应（确定性）
  - random:  生成随机但格式正确的响应
  - proxy:   转发到真实 LLM 并录制响应（用于生成 replay 数据）
"""
from fastapi import FastAPI, Request
import json
import hashlib
from pathlib import Path

app = FastAPI(title="SIA LLM Mock Server")

RESPONSES_DIR = Path("/app/responses")

# ─── 预定义响应库 ───
# responses/
#   classification/
#     vuln_cve_2026.json        ← CVE 漏洞类情报的分类响应
#     ransomware_attack.json    ← 勒索攻击类情报的分类响应
#     regulation_gdpr.json      ← 法规类情报的分类响应
#     ...
#   scoring/
#     high_severity.json        ← 高分情报的评分响应
#     low_severity.json         ← 低分情报的评分响应
#     ...
#   commentary/
#     automotive_vuln.json      ← 汽车行业漏洞的点评响应
#     ...

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    user_content = messages[-1]["content"] if messages else ""

    mode = os.environ.get("MOCK_MODE", "replay")

    if mode == "replay":
        response = match_replay_response(user_content)
    elif mode == "random":
        response = generate_random_response(user_content)
    elif mode == "proxy":
        response = await proxy_and_record(body)

    # 模拟延迟
    latency = int(os.environ.get("MOCK_LATENCY_MS", "500"))
    await asyncio.sleep(latency / 1000)

    return {
        "id": f"mock-{hashlib.md5(user_content.encode()).hexdigest()[:8]}",
        "choices": [{
            "message": {"role": "assistant", "content": json.dumps(response)},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
    }

def match_replay_response(content: str) -> dict:
    """根据输入内容的关键词匹配预定义响应"""
    # 判断是分类/评分/点评请求
    if "分类" in content or "classify" in content.lower():
        category = "classification"
    elif "评分" in content or "score" in content.lower():
        category = "scoring"
    elif "点评" in content or "commentary" in content.lower():
        category = "commentary"
    else:
        category = "default"

    # 按关键词匹配具体响应文件
    response_dir = RESPONSES_DIR / category
    for response_file in response_dir.glob("*.json"):
        keywords = response_file.stem.split("_")
        if any(kw in content.lower() for kw in keywords):
            return json.loads(response_file.read_text())

    # 默认响应
    return json.loads((RESPONSES_DIR / "default.json").read_text())
```

**Mock Server Docker Compose 集成（测试专用）：**

```yaml
# docker-compose.test.yaml — 测试专用 compose（CI 使用）

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: test
      MYSQL_DATABASE: sia_test
    tmpfs: /var/lib/mysql  # 内存文件系统，测试完即丢弃

  redis:
    image: redis:7-alpine
    tmpfs: /data

  milvus-standalone:
    image: milvusdb/milvus:v2.4-latest
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379

  etcd:
    image: quay.io/coreos/etcd:v3.5.11
    command: etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls=http://0.0.0.0:2379

  llm-mock:
    build: ./tools/llm-mock
    environment:
      MOCK_MODE: replay
      MOCK_LATENCY_MS: 50   # 测试中减小延迟

  push-mock:
    build: ./tools/push-mock
    # 模拟企微/飞书/邮件推送，记录推送内容供断言验证

  rss-mock:
    build: ./tools/rss-mock
    volumes:
      - ./tests/fixtures/rss:/app/feeds  # 本地 RSS XML 文件

  mailhog:
    image: mailhog/mailhog
    ports: ["8025:8025"]  # Web UI 查看测试邮件
```

### 35.3 测试数据工厂 [v3.0 新增，修正 TE-3, TE-12]

> **v2.0 不足：** 测试数据管理缺失。每个测试自己构造数据，重复且不一致。

```python
# tests/factories.py — 测试数据工厂

"""
使用 factory_boy 构建测试数据。
所有测试通过 Factory 创建数据，保证格式一致且可追溯。
"""
import factory
from datetime import datetime, timedelta
from src.models import IntelSource, Intelligence, Report, Subscriber

class IntelSourceFactory(factory.Factory):
    """情报源工厂"""
    class Meta:
        model = IntelSource

    name = factory.Sequence(lambda n: f"Test Source {n}")
    source_type = "rss"
    url = factory.LazyAttribute(lambda o: f"https://test-feed-{o.name.replace(' ', '-').lower()}.com/rss")
    status = "active"
    language = "zh"
    region = "cn"
    collect_frequency = 3600

class IntelligenceFactory(factory.Factory):
    """情报工厂"""
    class Meta:
        model = Intelligence

    title = factory.Sequence(lambda n: f"Test Intelligence {n}")
    content = factory.Faker('paragraph', nb_sentences=5, locale='zh_CN')
    source_id = factory.SubFactory(IntelSourceFactory)
    url = factory.LazyAttribute(lambda o: f"https://example.com/intel/{o.title.replace(' ', '-')}")
    published_at = factory.LazyFunction(lambda: datetime.now() - timedelta(hours=2))
    language = "zh"
    fingerprint = factory.LazyAttribute(
        lambda o: hashlib.sha256(f"{o.source_id}{o.url}{o.published_at}".encode()).hexdigest()
    )

    class Params:
        # 预设特征组合
        p0_vuln = factory.Trait(
            title="[CVE-2026-99999] Critical RCE in OpenSSL",
            primary_category="vulnerability",
            total_score=9.5,
            priority_level="P0",
        )
        p1_attack = factory.Trait(
            title="APT Group Targets Automotive Industry",
            primary_category="threat_activity",
            total_score=7.8,
            priority_level="P1",
        )
        regulation = factory.Trait(
            title="EU Cyber Resilience Act 实施细则发布",
            primary_category="regulation",
            total_score=6.5,
            priority_level="P2",
        )
        low_quality = factory.Trait(
            title="广告内容",
            content="这是一条广告",
            total_score=1.0,
            priority_level="P3",
        )

class ReportFactory(factory.Factory):
    """报告工厂"""
    class Meta:
        model = Report

    report_type = "daily"
    report_date = factory.LazyFunction(lambda: datetime.now().date())
    status = "completed"
    title = factory.LazyAttribute(lambda o: f"SIA 安全态势日报 {o.report_date}")

class SubscriberFactory(factory.Factory):
    """订阅者工厂"""
    class Meta:
        model = Subscriber

    name = factory.Faker('name', locale='zh_CN')
    role = "security_ops"
    email = factory.Faker('email')
    wechat_id = factory.Sequence(lambda n: f"wechat_{n}")
    preferred_channel = "wechat"
    timezone = "Asia/Shanghai"


# ─── Fixture 自动清理 ───

import pytest

@pytest.fixture(autouse=True)
def clean_test_data(db_session):
    """每个测试结束后自动清理测试数据"""
    yield
    db_session.rollback()
    # 或者使用 TRUNCATE（集成测试）
    # for table in reversed(Base.metadata.sorted_tables):
    #     db_session.execute(table.delete())
    # db_session.commit()

@pytest.fixture
def seed_intel(db_session):
    """种子情报数据：预设常用测试场景"""
    return {
        "p0_vuln": IntelligenceFactory.create(p0_vuln=True),
        "p1_attack": IntelligenceFactory.create(p1_attack=True),
        "regulation": IntelligenceFactory.create(regulation=True),
        "normal": IntelligenceFactory.create_batch(10),
    }
```

### 35.4 Testcontainers 集成测试架构 [v3.0 新增，修正 TE-4]

> **v2.0 不足：** testcontainers 一笔带过，未给出如何在 CI 中使用的设计。

```python
# tests/conftest.py — 集成测试基础设施

"""
集成测试使用 Testcontainers 启动真实数据库容器。
每个测试会话共享容器（Session Scope），测试间通过事务回滚隔离。
"""
import pytest
from testcontainers.mysql import MySqlContainer
from testcontainers.redis import RedisContainer
from testcontainers.milvus import MilvusContainer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

# ─── 容器生命周期（Session Scope，整个测试会话共享） ───

@pytest.fixture(scope="session")
def mysql_container():
    """启动 MySQL 容器"""
    with MySqlContainer("mysql:8.0") as mysql:
        # 执行数据库迁移
        engine = create_engine(mysql.get_connection_url())
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", mysql.get_connection_url())
        command.upgrade(alembic_cfg, "head")
        yield mysql

@pytest.fixture(scope="session")
def redis_container():
    """启动 Redis 容器"""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis

@pytest.fixture(scope="session")
def milvus_container():
    """启动 Milvus 容器"""
    with MilvusContainer("milvusdb/milvus:v2.4-latest") as milvus:
        yield milvus

# ─── 数据库会话（Function Scope，每个测试独立事务） ───

@pytest.fixture
def db_session(mysql_container):
    """每个测试一个事务，结束后自动回滚"""
    engine = create_engine(mysql_container.get_connection_url())
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()    # 回滚保证测试隔离
    connection.close()

# ─── Redis 客户端（每个测试自动清理） ───

@pytest.fixture
def redis_client(redis_container):
    """每个测试独立 Redis，结束后自动 FLUSHDB"""
    import redis
    client = redis.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
    )
    yield client
    client.flushdb()

# ─── Mock LLM（内存 Mock，不需要容器） ───

@pytest.fixture
def mock_llm(monkeypatch):
    """Mock LLM Gateway，返回确定性响应"""
    from tests.mocks.llm import MockLLMGateway
    mock = MockLLMGateway()
    monkeypatch.setattr("src.services.llm_gateway.LLMGateway", lambda: mock)
    return mock

# ─── 完整服务实例（集成测试用） ───

@pytest.fixture
def app_client(db_session, redis_client, mock_llm):
    """创建完整的 FastAPI TestClient"""
    from fastapi.testclient import TestClient
    from src.main import create_app

    app = create_app(
        db_session=db_session,
        redis_client=redis_client,
        llm_gateway=mock_llm,
    )
    return TestClient(app)
```

### 35.5 API 契约测试 [v3.0 新增，修正 TE-5]

> **v2.0 不足：** 服务间接口无契约保障。collector 和 analyzer 对消息格式的理解可能不一致。

```
API 契约测试策略：

1. OpenAPI Spec 作为 Single Source of Truth
   ┌─────────────────────────────────────────────────────┐
   │  src/api/openapi/                                   │
   │  ├── sia-gateway.yaml       ← 对外 API 规范         │
   │  ├── sia-internal.yaml      ← 服务间内部 API 规范    │
   │  └── schemas/                                       │
   │      ├── intelligence.yaml  ← 共享 Schema           │
   │      ├── report.yaml                                │
   │      └── common.yaml                                │
   └─────────────────────────────────────────────────────┘

2. 契约验证方式
   ┌──────────────┬──────────────────────────────────────┐
   │ 层面          │ 验证方式                               │
   ├──────────────┼──────────────────────────────────────┤
   │ API 端点     │ schemathesis 自动对 OpenAPI Spec      │
   │              │ 做 Property-Based Testing             │
   ├──────────────┼──────────────────────────────────────┤
   │ Redis 消息   │ Pydantic Model 强校验：生产者和消费者  │
   │              │ 使用同一 Schema 定义                   │
   ├──────────────┼──────────────────────────────────────┤
   │ 数据库       │ SQLAlchemy Model 与 Alembic 迁移      │
   │              │ 保持同步（CI 自动检测 drift）          │
   └──────────────┴──────────────────────────────────────┘

3. CI 中的契约测试
   - 每次 MR 自动运行 schemathesis 验证 API 实现是否符合 Spec
   - 每次 MR 自动检查 Redis 消息 Schema 是否前后兼容
   - 每次 MR 自动检查 DB Model 与最新迁移是否匹配
```

```python
# tests/contract/test_api_contract.py

"""
API 契约测试 — 验证 API 实现符合 OpenAPI Spec
"""
import schemathesis

schema = schemathesis.from_path(
    "src/api/openapi/sia-gateway.yaml",
    base_url="http://localhost:8080",
)

@schema.parametrize()
def test_api_contract(case):
    """自动生成请求，验证响应符合 Schema"""
    response = case.call()
    case.validate_response(response)
```

```python
# tests/contract/test_message_contract.py

"""
消息契约测试 — 验证 Redis Stream 消息格式一致性
"""
from src.schemas.messages import RawIntelMessage, AnalyzedIntelMessage

def test_raw_intel_message_contract():
    """collector 产出的消息格式，analyzer 必须能解析"""
    # 模拟 collector 产出的消息
    msg = RawIntelMessage(
        intel_id=1,
        title="Test",
        content="Test content",
        source_id=1,
        trace_id="test-trace-001",
    )
    # 序列化再反序列化，验证兼容性
    serialized = msg.model_dump_json()
    parsed = RawIntelMessage.model_validate_json(serialized)
    assert parsed.intel_id == msg.intel_id

def test_analyzed_message_backward_compatible():
    """新增字段不应破坏旧消费者"""
    # 旧格式消息（缺少新字段）
    old_format = '{"intel_id": 1, "scores": {}, "total_score": 5.0}'
    # 新版消费者应能解析旧格式（新字段有默认值）
    parsed = AnalyzedIntelMessage.model_validate_json(old_format)
    assert parsed.intel_id == 1
```

### 35.6 前端测试策略 [v3.0 新增，修正 TE-6]

> **v2.0 不足：** Vue 3 前端完全未涉及测试。前端 Bug 只能在上线后人工发现。

```
前端测试三层策略：

Layer 1: 组件单元测试（Vitest + Vue Test Utils）
─────────────────────────────────────────────────
  覆盖范围：
    - 每个 Vue 组件的渲染正确性
    - Props 传入后的行为
    - 事件触发与回调
    - 计算属性和响应式数据

  示例：
    tests/components/IntelCard.spec.ts
    tests/components/ScoreDisplay.spec.ts
    tests/components/ReportViewer.spec.ts

  工具：Vitest + @vue/test-utils + MSW (Mock Service Worker)

Layer 2: 页面集成测试（Vitest + MSW）
────────────────────────────────────
  覆盖范围：
    - 页面级数据加载流程
    - API 调用 → 列表渲染 → 分页/排序
    - 表单提交流程
    - 错误状态展示

  Mock 方式：MSW 拦截 HTTP 请求，返回预定义响应

Layer 3: E2E 测试（Playwright）
──────────────────────────────
  覆盖范围（关键用户路径）：
    - 登录 → 仪表盘加载 → 数据显示正确
    - 情报列表 → 搜索/筛选 → 查看详情 → 反馈
    - 报告中心 → 查看报告 → 审核通过
    - 情报源管理 → 新增 → 编辑 → 停用
    - 响应式布局（模拟移动端视口）

  执行方式：
    - CI 中对 staging 环境运行
    - 失败时自动截图和录屏
```

```typescript
// tests/e2e/dashboard.spec.ts — Playwright E2E 测试示例

import { test, expect } from '@playwright/test';

test.describe('仪表盘', () => {
  test.beforeEach(async ({ page }) => {
    // 使用测试账号登录
    await page.goto('/login');
    await page.fill('[data-testid="username"]', 'test_admin');
    await page.fill('[data-testid="password"]', 'test_pass');
    await page.click('[data-testid="login-btn"]');
    await page.waitForURL('/dashboard');
  });

  test('应显示态势灯和今日情报统计', async ({ page }) => {
    // 态势灯可见
    await expect(page.locator('[data-testid="status-light"]')).toBeVisible();
    // 统计卡片
    await expect(page.locator('[data-testid="intel-count"]')).toContainText(/\d+/);
    await expect(page.locator('[data-testid="p0-count"]')).toBeVisible();
  });

  test('情报列表应支持搜索和筛选', async ({ page }) => {
    await page.goto('/intelligence');
    // 搜索
    await page.fill('[data-testid="search-input"]', 'CVE-2026');
    await page.press('[data-testid="search-input"]', 'Enter');
    // 结果应包含关键词
    const results = page.locator('[data-testid="intel-item"]');
    await expect(results.first()).toContainText('CVE-2026');
  });

  test('移动端布局应正确响应', async ({ page }) => {
    // 设置移动端视口
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/dashboard');
    // 侧边栏应隐藏
    await expect(page.locator('[data-testid="sidebar"]')).not.toBeVisible();
    // 底部导航应可见
    await expect(page.locator('[data-testid="bottom-nav"]')).toBeVisible();
  });
});
```

### 35.7 Dify Workflow 测试方案 [v3.0 新增，修正 TE-11]

> **v2.0 不足：** Dify Workflow 作为核心编排层，但测试策略空白。

```
Dify Workflow 测试策略：

挑战：
  - Dify Workflow 通过 GUI 编排，不是代码，无法直接单元测试
  - Workflow 依赖 LLM 服务，输出不确定

测试方案：

1. Workflow API 测试（黑盒）
   ─────────────────────────
   通过 Dify 的 Workflow API 触发执行，验证输入输出

   POST /v1/workflows/run
   {
     "inputs": { "intel_text": "..." },
     "response_mode": "blocking"
   }

   验证：
   - 响应中包含期望的 JSON 字段
   - 分类在预定义列表内
   - 评分在 0-10 范围内
   - 响应时间 < 60s

2. Workflow 版本对比测试
   ─────────────────────────
   修改 Prompt 后，对比新旧版本在黄金数据集上的输出

   流程：
   a. 导出当前 Workflow (Dify DSL JSON)
   b. 修改 Prompt
   c. 在黄金数据集的 20 条样本上分别运行新旧版本
   d. 对比分类准确率和评分相关性
   e. 无退化 → 通过

3. Workflow 结构验证
   ─────────────────────────
   验证 Dify Workflow DSL 的结构完整性

   检查项：
   - 所有节点均已连接（无孤立节点）
   - LLM 节点配置了超时和错误处理
   - 输出变量映射完整
   - 必要的条件分支存在

4. Workflow 导出与版本管理
   ─────────────────────────
   - 每次 Workflow 变更后，导出 DSL JSON 存入 Git
   - 目录：dify/workflows/
   - 文件命名：{workflow_name}_v{version}.json
   - CI 中对 DSL 做结构验证
```

### 35.8 Redis Streams 测试辅助工具 [v3.0 新增，修正 TE-15]

> **v2.0 不足：** Redis Streams 是核心消息管道，但测试工具缺失。

```python
# tests/helpers/stream_helper.py — Redis Streams 测试辅助

"""
简化 Redis Streams 在测试中的操作：
  - 发送消息到 Stream
  - 等待消息被消费
  - 检查 DLQ
  - 验证 Consumer Group 状态
"""
import redis
import json
import time
from typing import Any

class StreamTestHelper:
    """Redis Streams 测试辅助类"""

    def __init__(self, redis_client: redis.Redis):
        self.r = redis_client

    def publish(self, stream: str, data: dict) -> str:
        """发送一条消息到 Stream，返回消息 ID"""
        return self.r.xadd(stream, {"data": json.dumps(data)})

    def publish_batch(self, stream: str, items: list[dict]) -> list[str]:
        """批量发送消息"""
        return [self.publish(stream, item) for item in items]

    def wait_for_consumed(
        self, stream: str, group: str,
        expected_count: int, timeout: float = 10.0
    ) -> bool:
        """等待消息被消费（ACK），超时返回 False"""
        start = time.time()
        while time.time() - start < timeout:
            info = self.r.xinfo_groups(stream)
            for g in info:
                if g["name"] == group:
                    pending = g.get("pending", 0)
                    if pending == 0:
                        return True
            time.sleep(0.1)
        return False

    def get_dlq_messages(self, dlq_stream: str = "dead_letter_stream") -> list[dict]:
        """读取 DLQ 中的所有消息"""
        messages = self.r.xrange(dlq_stream, "-", "+")
        return [json.loads(msg[1][b"data"]) for msg in messages]

    def get_pending_count(self, stream: str, group: str) -> int:
        """获取 Pending List 中的消息数"""
        info = self.r.xpending(stream, group)
        return info.get("pending", 0) if info else 0

    def drain_stream(self, stream: str) -> list[dict]:
        """读取并清空 Stream 中的所有消息"""
        messages = self.r.xrange(stream, "-", "+")
        if messages:
            self.r.xtrim(stream, maxlen=0)
        return [json.loads(msg[1][b"data"]) for msg in messages]

    def assert_message_in_stream(
        self, stream: str, expected: dict, key_fields: list[str] | None = None
    ):
        """断言 Stream 中存在匹配的消息"""
        messages = self.r.xrange(stream, "-", "+")
        for _, msg_data in messages:
            data = json.loads(msg_data[b"data"])
            if key_fields:
                if all(data.get(k) == expected.get(k) for k in key_fields):
                    return True
            elif data == expected:
                return True
        raise AssertionError(f"未找到匹配消息。Stream: {stream}, Expected: {expected}")
```

---

## 36. 测试执行与度量

### 36.1 测试覆盖率标准 [v3.0 新增，修正 TE-7]

```
测试覆盖率标准与 CI 门控：

┌──────────────────┬────────────┬───────────┬────────────────────┐
│ 层级              │ 覆盖率目标  │ CI 门控    │ 计算方式            │
├──────────────────┼────────────┼───────────┼────────────────────┤
│ 单元测试（Python）│ ≥ 80%      │ 强制       │ pytest-cov (line)  │
│ 单元测试（Vue）   │ ≥ 70%      │ 强制       │ vitest --coverage  │
│ 集成测试          │ ≥ 60%      │ 软性       │ 关键路径覆盖         │
│ E2E 测试         │ 不设百分比  │ 场景完成率 │ 20 场景通过 ≥ 18    │
└──────────────────┴────────────┴───────────┴────────────────────┘

覆盖率排除清单（不计入覆盖率）：
  - tests/ 目录本身
  - alembic/versions/ 迁移脚本
  - src/scripts/ 一次性脚本
  - __main__.py 入口文件
  - 生成的代码（OpenAPI client 等）

覆盖率追踪：
  - CI 中生成 Cobertura XML → GitLab MR 中显示覆盖率变化
  - 覆盖率下降 > 2% 的 MR → 强制人工审核
  - 月度覆盖率趋势图 → Grafana SIA-Test-Quality Dashboard
```

### 36.2 部署后冒烟测试 [v3.0 新增，修正 TE-8]

> **v2.0 不足：** 部署后无自动化验证。可能部署成功但功能异常。

```bash
#!/bin/bash
# scripts/post-deploy-smoke.sh — 部署后冒烟测试
set -euo pipefail

ENV=${1:-staging}
BASE_URL="https://sia-${ENV}.internal.company.com"
FAILED=0
TOTAL=0

check() {
    TOTAL=$((TOTAL + 1))
    local name=$1 cmd=$2 expected=$3
    echo -n "  [${TOTAL}] ${name}... "
    result=$(eval "$cmd" 2>/dev/null) || result="ERROR"
    if echo "$result" | grep -q "$expected"; then
        echo "PASS"
    else
        echo "FAIL (got: ${result:0:100})"
        FAILED=$((FAILED + 1))
    fi
}

echo "===== SIA Smoke Test (ENV=${ENV}) ====="

# ─── 健康检查 ───
echo "--- Health Checks ---"
for svc in gateway collector analyzer reporter scheduler; do
    check "${svc} liveness" \
        "curl -sf ${BASE_URL}/api/${svc}/healthz" \
        "alive"
    check "${svc} readiness" \
        "curl -sf ${BASE_URL}/api/${svc}/readyz" \
        "ready"
done

# ─── API 可用性 ───
echo "--- API Availability ---"
check "GET /api/v1/intelligence" \
    "curl -sf -o /dev/null -w '%{http_code}' ${BASE_URL}/api/v1/intelligence?limit=1" \
    "200"

check "GET /api/v1/sources" \
    "curl -sf -o /dev/null -w '%{http_code}' ${BASE_URL}/api/v1/sources" \
    "200"

check "GET /api/v1/reports/latest" \
    "curl -sf -o /dev/null -w '%{http_code}' ${BASE_URL}/api/v1/reports/latest" \
    "200"

# ─── 数据库连通性 ───
echo "--- Database Connectivity ---"
check "MySQL connection" \
    "curl -sf ${BASE_URL}/api/v1/health/db" \
    "connected"

check "Redis connection" \
    "curl -sf ${BASE_URL}/api/v1/health/redis" \
    "connected"

check "Milvus connection" \
    "curl -sf ${BASE_URL}/api/v1/health/milvus" \
    "connected"

# ─── LLM 可用性 ───
echo "--- LLM Availability ---"
check "LLM endpoint" \
    "curl -sf ${BASE_URL}/api/v1/health/llm" \
    "available"

# ─── Web 前端 ───
echo "--- Web Frontend ---"
check "Web index.html" \
    "curl -sf -o /dev/null -w '%{http_code}' ${BASE_URL}/" \
    "200"

check "Web assets" \
    "curl -sf -o /dev/null -w '%{http_code}' ${BASE_URL}/assets/" \
    "200"

# ─── 结果 ───
echo ""
echo "===== Results: $((TOTAL - FAILED))/${TOTAL} passed ====="
if [ $FAILED -gt 0 ]; then
    echo "❌ 冒烟测试失败！请检查部署状态。"
    exit 1
else
    echo "✅ 所有冒烟测试通过。"
fi
```

### 36.3 性能测试场景 [v3.0 新增，修正 TE-9]

> **v2.0 不足：** 提到 Locust/K6 但无具体测试场景和脚本。

```python
# tests/performance/locustfile.py — 性能测试场景

"""
SIA 性能测试场景
使用 Locust 执行，支持分布式负载生成。
运行：locust -f tests/performance/locustfile.py --host=https://sia-staging.internal.company.com
"""
from locust import HttpUser, task, between, tag

class SIAAPIUser(HttpUser):
    """模拟 API 用户访问模式"""
    wait_time = between(1, 3)

    @tag("read")
    @task(10)
    def browse_intelligence_list(self):
        """浏览情报列表（最高频操作）"""
        self.client.get("/api/v1/intelligence?page=1&size=20")

    @tag("read")
    @task(5)
    def view_intelligence_detail(self):
        """查看情报详情"""
        self.client.get("/api/v1/intelligence/1")

    @tag("read")
    @task(3)
    def search_intelligence(self):
        """搜索情报"""
        self.client.get("/api/v1/intelligence/search?q=CVE&page=1&size=20")

    @tag("read")
    @task(3)
    def view_dashboard(self):
        """查看仪表盘数据"""
        self.client.get("/api/v1/dashboard/summary")

    @tag("read")
    @task(2)
    def view_report(self):
        """查看报告"""
        self.client.get("/api/v1/reports/latest?type=daily")

    @tag("write")
    @task(1)
    def submit_feedback(self):
        """提交反馈"""
        self.client.post("/api/v1/feedback", json={
            "intel_id": 1,
            "rating": "useful",
            "comment": "Good analysis"
        })

class SIAPipelineUser(HttpUser):
    """模拟情报处理管线压力"""
    wait_time = between(0.5, 1)

    @tag("pipeline")
    @task
    def trigger_collection(self):
        """触发采集任务"""
        self.client.post("/api/v1/internal/collect", json={
            "source_id": 1,
            "force": True
        })
```

```
性能测试基准与场景：

┌──────────────────┬──────────┬──────────┬──────────────────────┐
│ 场景              │ 并发用户  │ 持续时间  │ SLA                   │
├──────────────────┼──────────┼──────────┼──────────────────────┤
│ 日常负载          │ 20       │ 30 min   │ P99 < 500ms          │
│                  │          │          │ 错误率 < 0.1%         │
├──────────────────┼──────────┼──────────┼──────────────────────┤
│ 高峰负载          │ 50       │ 15 min   │ P99 < 1s             │
│ (重大安全事件)    │          │          │ 错误率 < 1%           │
├──────────────────┼──────────┼──────────┼──────────────────────┤
│ 管线压力          │ N/A      │ 60 min   │ 2000 条/天处理完成    │
│ (情报涌入)       │          │          │ 无消息积压 > 5000     │
├──────────────────┼──────────┼──────────┼──────────────────────┤
│ 长稳测试          │ 10       │ 24 h     │ 无内存泄漏            │
│                  │          │          │ 无连接泄漏            │
└──────────────────┴──────────┴──────────┴──────────────────────┘

执行频率：
  - 日常负载：每次重大版本发布前
  - 管线压力：每月
  - 长稳测试：每季度
```

### 36.4 测试报告与度量 [v3.0 新增，修正 TE-10]

```
测试度量仪表盘（Grafana: SIA-Test-Quality）：

核心度量指标：
  ┌──────────────────────┬──────────────────────────────┐
  │ 指标                  │ 数据来源                       │
  ├──────────────────────┼──────────────────────────────┤
  │ 单元测试通过率         │ CI JUnit XML                  │
  │ 集成测试通过率         │ CI JUnit XML                  │
  │ E2E 测试场景完成率     │ CI JUnit XML                  │
  │ 代码覆盖率趋势         │ CI Cobertura XML              │
  │ Prompt 回归测试分数    │ CI 自定义 metric               │
  │ LLM Schema 校验通过率 │ Prometheus                     │
  │ 冒烟测试通过率         │ 部署后自动执行结果              │
  │ 性能测试 P99 延迟趋势  │ Locust 报告                    │
  │ Bug 趋势（按严重程度） │ Issue Tracker                  │
  │ MTTR（故障修复时间）   │ Issue Tracker                  │
  └──────────────────────┴──────────────────────────────┘

CI 中测试报告生成：
  - JUnit XML → GitLab MR 测试报告标签页
  - 覆盖率报告 → GitLab MR 覆盖率变化指示器
  - 性能报告 → MinIO 存储 + Grafana 可视化
  - 截图/录屏 → CI Artifact（Playwright E2E 失败时）
```

### 36.5 测试金字塔执行策略 [v3.0 新增，修正 TE-13]

```
测试金字塔与执行时机：

                    ╱╲
                   ╱  ╲         E2E Tests
                  ╱    ╲        - 20 场景
                 ╱  E2E ╲       - 每周 + staging 部署后
                ╱────────╲      - 耗时 ~30 分钟
               ╱          ╲
              ╱ Integration ╲   Integration Tests
             ╱              ╲   - ~100 个用例
            ╱────────────────╲  - 每日 CI + MR
           ╱                  ╲ - 耗时 ~10 分钟
          ╱    Unit Tests      ╲
         ╱                      ╲ Unit Tests
        ╱────────────────────────╲ - ~500 个用例
       ╱   最大覆盖 / 最快速度     ╲ - 每次 push
      ╱──────────────────────────────╲ - 耗时 ~2 分钟

执行策略：
  ┌────────────┬─────────────┬───────────────────────────────┐
  │ 触发时机    │ 运行范围     │ 阻断条件                       │
  ├────────────┼─────────────┼───────────────────────────────┤
  │ git push   │ Unit        │ 覆盖率 < 80% → 阻断            │
  │ MR 创建    │ Unit + Int  │ 任何测试失败 → 阻断 Merge       │
  │ main 合并  │ Unit + Int  │ 失败 → 阻断部署                │
  │            │ + Build     │                               │
  │ 部署staging│ Smoke       │ 失败 → 阻断 prod 部署          │
  │ 每周六     │ E2E 全量    │ 失败 → 创建 Issue              │
  │ 每月       │ Performance │ 超 SLA → 创建 Issue            │
  │ Prompt变更 │ 回归基线     │ 准确率<85% → 阻断 Prompt 上线  │
  └────────────┴─────────────┴───────────────────────────────┘
```

### 36.6 多语言处理测试用例集 [v3.0 新增，修正 TE-16]

```
多语言处理测试覆盖：

┌──────────────────┬──────────────────────────────────────────────┐
│ 测试场景          │ 验证要点                                       │
├──────────────────┼──────────────────────────────────────────────┤
│ 纯中文情报        │ 正确分类/评分，无乱码                            │
│ 纯英文情报        │ 正确分类/评分，翻译为中文摘要                     │
│ 中英混合情报      │ 正确处理，不因混合语言导致分类错误                 │
│ 日文/韩文情报     │ 正确识别语言 → 标记待翻译 → 翻译后分析             │
│ 德文/法文法规     │ 翻译质量（EU 法规专业术语）                       │
│ 繁体中文          │ 正确处理，不与简体混淆                            │
│ 含特殊字符        │ emoji、技术符号、CVE 编号不被破坏                  │
│ 超长正文          │ 正确截断，不溢出/OOM                             │
│ 纯符号/乱码       │ 质量门控拦截，不进入分析管线                      │
│ RTL 语言（阿拉伯）│ 正确存储和显示（预留，Phase 3+）                  │
└──────────────────┴──────────────────────────────────────────────┘

测试数据：
  tests/fixtures/multilang/
  ├── zh_vuln_cve.txt           ← 中文漏洞情报
  ├── en_ransomware_report.txt  ← 英文勒索攻击报告
  ├── zh_en_mixed_advisory.txt  ← 中英混合安全通告
  ├── ja_security_news.txt      ← 日文安全新闻
  ├── de_regulation_eu.txt      ← 德文 EU 法规
  ├── zh_hant_advisory.txt      ← 繁体中文安全通告
  ├── special_chars.txt         ← 特殊字符压力测试
  └── garbage_encoding.txt      ← 乱码（应被拦截）
```

### 36.7 安全功能测试场景 [v3.0 新增，修正 TE-17]

```
安全功能测试矩阵：

┌────┬──────────────────────┬───────────────────────────────────────┬─────────┐
│ #  │ 测试场景              │ 测试方法                                │ 预期结果 │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 1  │ Prompt 注入攻击       │ 在情报正文中嵌入 "ignore previous      │ 输出校验 │
│    │                      │ instructions" 等注入指令               │ 通过     │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 2  │ SQL 注入              │ API 参数中传入 ' OR 1=1 --           │ 参数     │
│    │                      │                                       │ 校验拦截 │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 3  │ XSS 攻击             │ 情报标题中插入 <script>alert(1)        │ 转义后   │
│    │                      │ </script>                             │ 渲染     │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 4  │ 越权访问              │ 用只读角色尝试修改评分模型              │ 403      │
│    │                      │                                       │ Forbidden│
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 5  │ TLP:RED 越权          │ 业务线角色尝试访问 TLP:RED 情报         │ 403      │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 6  │ 暴力破解              │ 连续 10 次错误密码登录                  │ 账户锁定 │
│    │                      │                                       │ + 告警   │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 7  │ API 限速              │ 单 IP 超 60 req/min                   │ 429      │
│    │                      │                                       │ 限速     │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 8  │ 审计日志完整性         │ 关键操作后检查审计日志是否写入          │ 日志完整 │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 9  │ 敏感数据泄露          │ API 响应中搜索密码/Key/Token 模式      │ 无泄露   │
├────┼──────────────────────┼───────────────────────────────────────┼─────────┤
│ 10 │ CSRF 防护             │ 无 CSRF Token 的状态修改请求           │ 403      │
└────┴──────────────────────┴───────────────────────────────────────┴─────────┘

执行方式：
  - #1-#5: 自动化测试（pytest）
  - #6-#10: 自动化测试（pytest + Trivy + OWASP ZAP）
  - 完整安全扫描：每月运行 OWASP ZAP 全扫描
```

---

# 第十三部分：运维操作手册

## 37. 日常运维

### 37.1 日常运维 SOP [v3.0 新增，修正 OP-1]

> **v2.0 不足：** Runbook 仅覆盖故障场景，日常巡检、备份、清理无标准流程。

```
日常运维 SOP 总览：

┌──────────┬──────────┬─────────────────────────────────────────┐
│ 频率      │ 任务      │ 操作要点                                  │
├──────────┼──────────┼─────────────────────────────────────────┤
│ 每日      │ 巡检      │ 1. 检查所有 Pod 状态 (Running?)           │
│          │          │ 2. 检查日报是否准时推送                     │
│          │          │ 3. 检查采集源健康率 (≥ 90%?)               │
│          │          │ 4. 检查 DLQ 消息数 (= 0?)                 │
│          │          │ 5. 检查 Grafana 告警面板                   │
│          │          │ 执行：make ops-daily-check ENV=prod       │
├──────────┼──────────┼─────────────────────────────────────────┤
│ 每周      │ 质量审查  │ 1. 抽检 20 条 LLM 分析结果                │
│          │          │ 2. 检查误杀/漏报情况                       │
│          │          │ 3. 检查反馈满意度趋势                      │
│          │          │ 4. 检查磁盘使用趋势                        │
│          │          │ 执行：make ops-weekly-review ENV=prod     │
├──────────┼──────────┼─────────────────────────────────────────┤
│ 每月      │ 维护      │ 1. 数据清理任务确认（CronJob 日志）        │
│          │          │ 2. 审计日志哈希链校验                      │
│          │          │ 3. 安全扫描（Trivy + ZAP）                │
│          │          │ 4. 容量趋势分析                            │
│          │          │ 5. 依赖版本更新评估                        │
│          │          │ 执行：make ops-monthly-maintenance ENV=prod│
├──────────┼──────────┼─────────────────────────────────────────┤
│ 每季度    │ Review   │ 1. 容量规划 Review（§37.8）               │
│          │          │ 2. 混沌工程演练                            │
│          │          │ 3. 灾备恢复演练                            │
│          │          │ 4. 安全渗透测试                            │
│          │          │ 5. SLO 达成率回顾                         │
└──────────┴──────────┴─────────────────────────────────────────┘
```

### 37.2 运维自动化脚本库 [v3.0 新增，修正 OP-2]

```
运维脚本清单（scripts/ops/）：

┌────┬─────────────────────────┬────────────────────────────────────┐
│ #  │ 脚本                     │ 功能                                │
├────┼─────────────────────────┼────────────────────────────────────┤
│ 1  │ daily-check.sh           │ 日巡检：Pod/推送/采集/DLQ/告警       │
│ 2  │ weekly-review.sh         │ 周审查：LLM 质量/反馈/磁盘趋势       │
│ 3  │ monthly-maintenance.sh   │ 月维护：清理确认/审计/扫描/容量       │
│ 4  │ backup-verify.sh         │ 验证备份完整性（恢复到临时库测试）    │
│ 5  │ source-health-report.sh  │ 生成采集源健康报告                   │
│ 6  │ llm-quality-report.sh    │ 生成 LLM 输出质量周报                │
│ 7  │ stream-status.sh         │ 查看 Redis Stream 各队列状态         │
│ 8  │ replay-dlq.sh            │ 重放 DLQ 消息到原 Stream             │
│ 9  │ force-collect.sh         │ 手动触发指定源的强制采集              │
│ 10 │ force-report.sh          │ 手动触发日报/周报生成                 │
│ 11 │ scale-service.sh         │ 手动调整服务副本数                    │
│ 12 │ rotate-secret.sh         │ 密钥轮换（生成新值 + 更新 Secret）   │
│ 13 │ export-intel.sh          │ 导出情报数据（CSV/STIX）             │
│ 14 │ import-sources.sh        │ 批量导入情报源配置                    │
│ 15 │ db-maintenance.sh        │ 数据库维护（OPTIMIZE TABLE 等）      │
└────┴─────────────────────────┴────────────────────────────────────┘

使用方式：
  make ops-daily-check ENV=prod        # 通过 Makefile 调用
  ./scripts/ops/daily-check.sh prod    # 或直接执行
```

### 37.3 故障诊断工具包 [v3.0 新增，修正 OP-3]

```
故障诊断 One-Liner 命令集：

# ─── Pod 状态 ───
# 查看异常 Pod
kubectl get pods -n sia-prod | grep -v Running | grep -v Completed

# 查看 Pod 事件（排查启动失败）
kubectl describe pod <pod-name> -n sia-prod | tail -20

# 查看 Pod 资源使用
kubectl top pods -n sia-prod --sort-by=memory

# ─── 日志快速排查 ───
# 最近 10 分钟错误日志
kubectl logs -n sia-prod -l app=sia-analyzer --since=10m | grep ERROR

# 按 trace_id 追踪
kubectl logs -n sia-prod --all-containers=true --since=1h | grep "trace_id=abc-123"

# ─── Redis Streams 状态 ───
# 查看各 Stream 长度
redis-cli -h redis-master XLEN raw_intel_stream
redis-cli -h redis-master XLEN analyzed_stream
redis-cli -h redis-master XLEN dead_letter_stream

# 查看 Consumer Group 消费进度
redis-cli -h redis-master XINFO GROUPS raw_intel_stream

# 查看 Pending 消息
redis-cli -h redis-master XPENDING raw_intel_stream analyzer-group

# ─── MySQL 诊断 ───
# 慢查询
mysql -e "SELECT * FROM mysql.slow_log ORDER BY start_time DESC LIMIT 10;"

# 连接数
mysql -e "SHOW STATUS LIKE 'Threads_connected';"

# 表空间使用
mysql -e "SELECT table_name, ROUND(data_length/1024/1024, 2) AS 'Size_MB'
          FROM information_schema.tables
          WHERE table_schema='sia' ORDER BY data_length DESC;"

# ─── Milvus 诊断 ───
# 集合状态
python -c "from pymilvus import connections, Collection
connections.connect(host='milvus', port='19530')
c = Collection('intel_vectors')
print(f'Count: {c.num_entities}, Loaded: {c.is_loaded}')"

# ─── 综合诊断脚本 ───
# make diagnose ENV=prod  # 运行完整诊断
```

### 37.4 版本升级 SOP [v3.0 新增，修正 OP-4]

```
版本升级标准操作流程：

升级前（T-1 天）：
  □ 1. 阅读 CHANGELOG，了解变更内容
  □ 2. 确认数据库迁移内容（alembic history）
  □ 3. 在 staging 环境完成升级验证
  □ 4. staging 冒烟测试通过
  □ 5. 通知相关方（安全团队、运维值班）

升级执行（维护窗口内）：
  □ 1. 通知用户（企微/飞书群发维护通知）
  □ 2. 运行前置检查
       make pre-deploy-check ENV=prod
  □ 3. 创建数据库备份
       make db-backup ENV=prod
  □ 4. 记录当前版本
       helm history sia -n sia-prod | tail -1
  □ 5. 执行部署
       make deploy ENV=prod IMAGE_TAG=v1.3.0
  □ 6. 等待 Pod 滚动更新完成
       kubectl rollout status deploy -n sia-prod --timeout=10m
  □ 7. 运行冒烟测试
       make smoke-test ENV=prod
  □ 8. 检查关键指标（Grafana 5 分钟）
       - API 错误率无升高
       - LLM 调用正常
       - 无异常告警

升级后：
  □ 1. 观察 30 分钟稳定性
  □ 2. 通知用户升级完成
  □ 3. 记录升级事件到运维日志

回滚条件（满足任一则回滚）：
  ✗ 冒烟测试失败
  ✗ API 错误率 > 5%
  ✗ LLM 调用全部失败
  ✗ 关键功能不可用

回滚执行：
  make rollback ENV=prod
  # 如涉及数据库回退：
  make db-rollback ENV=prod
```

### 37.5 证书与密钥轮换 SOP [v3.0 新增，修正 OP-5]

```
证书/密钥轮换计划：

┌──────────────────┬──────────┬─────────────────────────────────┐
│ 类型              │ 轮换周期  │ 轮换方式                          │
├──────────────────┼──────────┼─────────────────────────────────┤
│ TLS 证书（Ingress）│ 自动      │ cert-manager + Let's Encrypt    │
│                  │          │ 或内部 CA 自动续期               │
├──────────────────┼──────────┼─────────────────────────────────┤
│ MySQL 密码        │ 90 天    │ 1. 生成新密码                    │
│                  │          │ 2. ALTER USER 修改 MySQL 密码    │
│                  │          │ 3. 更新 Sealed Secret            │
│                  │          │ 4. Rolling restart 应用 Pod      │
├──────────────────┼──────────┼─────────────────────────────────┤
│ Redis 密码        │ 90 天    │ 同 MySQL，通过 CONFIG SET        │
├──────────────────┼──────────┼─────────────────────────────────┤
│ LLM API Key      │ 180 天   │ 1. 在 LLM 平台生成新 Key         │
│                  │          │ 2. 更新 Sealed Secret            │
│                  │          │ 3. Rolling restart sia-gateway   │
├──────────────────┼──────────┼─────────────────────────────────┤
│ 企微/飞书 Webhook │ 按需      │ 在管理后台重新生成 URL           │
├──────────────────┼──────────┼─────────────────────────────────┤
│ MinIO Access Key │ 180 天    │ mc admin user password          │
└──────────────────┴──────────┴─────────────────────────────────┘

到期预警：
  - cert-manager 自动管理 TLS 证书续期
  - 密码/Key 在 ConfigMap 中记录 rotation_date
  - CronJob 每周检查：距下次轮换 < 14 天 → 告警
```

### 37.6 依赖版本兼容矩阵 [v3.0 新增，修正 OP-6]

```
依赖版本兼容矩阵：

┌──────────────┬───────────────┬──────────────┬──────────────────┐
│ 依赖          │ 测试通过版本   │ 最低版本      │ 升级注意事项       │
├──────────────┼───────────────┼──────────────┼──────────────────┤
│ Python       │ 3.12.x        │ 3.11         │ 3.11 → 3.12 安全 │
│ MySQL        │ 8.0.x         │ 8.0.30       │ 8.0 → 8.4 需测试 │
│ Redis        │ 7.2.x         │ 7.0          │ 注意 Stream 命令  │
│ Milvus       │ 2.4.x         │ 2.3          │ 2.3→2.4 索引兼容  │
│ MinIO        │ RELEASE 2024  │ 2023-06      │ API 兼容          │
│ Dify         │ 0.8.x         │ 0.6          │ Workflow DSL 格式 │
│ ES (可选)    │ 8.12.x        │ 8.8          │ 索引映射兼容       │
│ Neo4j (可选) │ 5.x           │ 5.0          │ Cypher 语法       │
│ Nginx Ingress│ 1.10.x        │ 1.8          │ 注解语法变更       │
│ Helm         │ 3.14.x        │ 3.12         │ Chart API v2      │
│ ArgoCD       │ 2.10.x        │ 2.8          │ App Spec 兼容     │
└──────────────┴───────────────┴──────────────┴──────────────────┘

依赖升级策略：
  - Patch 版本：自动合并（Renovate/Dependabot）
  - Minor 版本：CI 通过后自动合并
  - Major 版本：手动评估 + staging 验证 + 人工审批
```

### 37.7 值班轮换与告警升级制度 [v3.0 新增，修正 OP-7]

```
值班与告警升级制度：

值班安排：
  - 主值班：安全运营团队（周轮换）
  - 副值班：DevOps 团队（周轮换）
  - 值班表维护在企业日历系统中
  - 每周一上午交接，同步上周告警和待处理事项

告警升级链：
  ┌──────────┬──────────────────┬──────────────────────────┐
  │ 级别      │ 触发条件          │ 通知对象 + 动作            │
  ├──────────┼──────────────────┼──────────────────────────┤
  │ P4 Info  │ 提示性信息        │ 企微运维群（仅记录）       │
  ├──────────┼──────────────────┼──────────────────────────┤
  │ P3 Warn  │ 非关键异常        │ 主值班（企微通知）         │
  │          │ (采集源失败等)    │ 工作时间内处理即可         │
  ├──────────┼──────────────────┼──────────────────────────┤
  │ P2 High  │ 功能降级          │ 主值班（企微 + 短信）      │
  │          │ (LLM 熔断等)     │ 30 分钟内响应              │
  ├──────────┼──────────────────┼──────────────────────────┤
  │ P1 Critical│ 核心功能不可用   │ 主+副值班 + 团队 Lead     │
  │          │ (日报未推送等)    │ 15 分钟内响应              │
  │          │ 30min 未响应 →   │ 升级到安全负责人           │
  ├──────────┼──────────────────┼──────────────────────────┤
  │ P0 Emergency│ 全系统宕机     │ 所有相关人 + 管理层       │
  │          │                  │ 5 分钟内响应               │
  │          │ 15min 未响应 →   │ 电话呼叫                   │
  └──────────┴──────────────────┴──────────────────────────┘
```

### 37.8 季度容量 Review 机制 [v3.0 新增，修正 OP-8]

```
季度容量 Review 流程：

Review 内容：
  1. 过去 90 天资源使用趋势
     - CPU / Memory / Disk 各 Pod 使用率趋势图
     - 增长斜率预测：按当前增速，何时触及上限？

  2. 数据增长趋势
     - MySQL 表行数增长速率
     - Milvus 向量数量增长速率
     - MinIO 存储增长速率
     - 对比数据清理任务的效果

  3. LLM 用量趋势
     - Token 消耗趋势
     - 调用频次趋势
     - 模型成本估算

  4. 容量规划建议
     - 是否需要扩容？
     - 是否需要引入 ES / Neo4j（Phase 3 条件是否成熟）？
     - 数据保留策略是否需要调整？

  5. 成本优化机会
     - 冷数据归档比例
     - 闲置资源回收
     - LLM 缓存命中率（可降低调用量）

输出：
  - 容量 Review 报告（1-2 页）
  - 下季度资源规划建议
  - 需审批的扩容/采购需求

参与者：
  - DevOps 团队（出具数据）
  - 安全团队 Lead（评估业务增长）
  - 架构师（技术决策）
```

---

# 附录

## 附录 A-H

（同 v2.0，此处省略。）

## 附录 I：v2.0 → v3.0 完整变更索引

| 章节 | 变更类型 | 变更编号 | 描述 |
|------|---------|---------|------|
| §32.1 | 新增 | DO-1 | Helm Chart 完整设计 |
| §32.2 | 新增 | DO-2, DO-10 | 容器构建策略 + 镜像版本策略 |
| §32.3 | 新增 | DO-3 | docker-compose 本地开发环境 |
| §32.4 | 新增 | DO-5 | 三环境分层策略 (dev/staging/prod) |
| §32.5 | 新增 | DO-9 | Makefile 一键操作脚本 |
| §32.6 | 新增 | DO-14 | 服务依赖启动顺序 (initContainers) |
| §33 | 新增 | DO-4 | CI/CD Pipeline 完整设计 |
| §33.3 | 新增 | DO-12 | 部署前置检查清单 |
| §33.4 | 新增 | DO-8 | ArgoCD GitOps 工作流 |
| §34.1 | 新增 | DO-6 | Alembic 数据库迁移管理 |
| §34.2 | 新增 | DO-7 | Sealed Secrets 管理 |
| §34.3 | 新增 | DO-13 | 一键回滚 SOP |
| §34.4 | 新增 | DO-15 | Grafana Dashboard 即代码 |
| §34.5 | 新增 | DO-16 | 日志采集管线 |
| §35.1 | 新增 | TE-1, TE-18 | 测试环境架构 + 数据脱敏 |
| §35.2 | 新增 | TE-2, TE-14 | Mock 策略 + LLM Mock Server |
| §35.3 | 新增 | TE-3, TE-12 | TestDataFactory + 自动清理 |
| §35.4 | 新增 | TE-4 | Testcontainers 集成测试 |
| §35.5 | 新增 | TE-5 | API 契约测试 |
| §35.6 | 新增 | TE-6 | 前端测试策略 (Vitest + Playwright) |
| §35.7 | 新增 | TE-11 | Dify Workflow 测试方案 |
| §35.8 | 新增 | TE-15 | Redis Streams 测试辅助工具 |
| §36.1 | 新增 | TE-7 | 测试覆盖率标准 + CI 门控 |
| §36.2 | 新增 | TE-8 | 部署后冒烟测试 |
| §36.3 | 新增 | TE-9 | 性能测试场景 + 脚本模板 |
| §36.4 | 新增 | TE-10 | 测试报告仪表盘 |
| §36.5 | 新增 | TE-13 | 测试金字塔执行策略 |
| §36.6 | 新增 | TE-16 | 多语言处理测试用例集 |
| §36.7 | 新增 | TE-17 | 安全功能测试场景 |
| §37.1 | 新增 | OP-1 | 日常运维 SOP |
| §37.2 | 新增 | OP-2 | 运维自动化脚本库 |
| §37.3 | 新增 | OP-3 | 故障诊断工具包 |
| §37.4 | 新增 | OP-4 | 版本升级 SOP |
| §37.5 | 新增 | OP-5 | 证书与密钥轮换 SOP |
| §37.6 | 新增 | OP-6 | 依赖版本兼容矩阵 |
| §37.7 | 新增 | OP-7 | 值班轮换与告警升级制度 |
| §37.8 | 新增 | OP-8 | 季度容量 Review 机制 |

---

> **文档结束**
>
> v3.0 在 v1.0 架构设计 + v2.0 安全/可靠性加固的基础上，从 **DevOps 工程师**（部署自动化/环境管理/CI-CD）、**测试工程师**（测试基础设施/Mock/覆盖率/自动化）、**一线运维**（日常 SOP/诊断工具/升级流程）三个视角进行系统性深度审视。
>
> 核心目标：
> - **5 分钟上手**：新成员 `make dev-up` 一键启动全栈开发环境
> - **一键部署**：`make deploy ENV=prod` 完成从检查到部署到冒烟测试的全流程
> - **测试无盲区**：从单元测试到 E2E，从 LLM Mock 到 Prompt 回归，覆盖所有关键路径
> - **运维有据可依**：每个操作有 SOP，每个故障有诊断命令，每个告警有升级路径
>
> 与 v2.0 的关系：v3.0 是增量改进。v2.0 的架构设计、安全加固、业务逻辑保持不变，v3.0 补充的是"设计好之后如何落地"——部署怎么做、测试怎么跑、日常怎么维护。
