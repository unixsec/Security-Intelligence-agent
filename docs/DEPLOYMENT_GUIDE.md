# 企业 Kubernetes 部署指南

> **这是权威部署文档。** SIA v0.2.0 面向企业 K8s 集群落地，采用**集中化配置 + 一键脚本**的流程：所有环境差异收敛在单个 `deployment.config.yaml`，脚本自动生成 Helm values 与 Secret 清单。

## 1. 前置条件

### 1.1 集群
- Kubernetes **1.27+**，启用 `NetworkPolicy` 准入
- Ingress 控制器（推荐 `ingress-nginx`）
- [`cert-manager`](https://cert-manager.io/) —— 用于证书自动签发
- （可选）OPA Gatekeeper、Falco —— 详见 [`SECURITY.md`](./SECURITY.md)

### 1.2 外部服务
部署前必须已就位：

| 服务 | 最低版本 | 要求 |
|---|---|---|
| MySQL | 8.0 | 专用数据库 + 账号；建议 TLS `required` |
| Redis | 7 | 设置密码；建议 TLS |
| Milvus | 2.4 | 用于语义去重（可选但推荐） |
| MinIO（S3 兼容） | 2024+ | 报告归档（可选，若 `minio.enabled=false` 可省） |
| SMTP | 任意 | 邮件推送（可选） |
| OTLP Collector | 任意 | 链路追踪（可选） |

### 1.3 部署工作站工具

| 工具 | 版本 | 备注 |
|---|---|---|
| `kubectl` | ≥ 1.27 | 已 `current-context` 指向目标集群 |
| `helm` | ≥ 3.12 | |
| `docker` | ≥ 24 | 仅在本机构建镜像时需要，CI 场景可省 |
| `yq` | mikefarah v4 | `go install github.com/mikefarah/yq/v4@latest` |
| `openssl` | 3.x | 生成 JWT / API key |

## 2. 部署流程总览

```
┌─────────────────────────────────────────────────────────┐
│ 1. cp template → deployment.config.yaml                 │
│ 2. 填占位符  (<K8S_CONTEXT>, <MYSQL_HOST>, ...)         │
│ 3. configure.sh --generate-secrets                      │
│     ├─ 生成 deploy/helm/sia/values-prod.yaml            │
│     └─ 生成 deploy/rendered/sia-secrets.yaml  (600)     │
│ 4. deploy-k8s.sh                                        │
│     ├─ 构建 Docker 镜像（可跳过）                       │
│     ├─ 推送到 registry（可跳过）                        │
│     ├─ kubectl apply -f rendered/sia-secrets.yaml       │
│     ├─ helm upgrade --install                           │
│     ├─ post-install Job: alembic migrate + seed         │
│     └─ 冒烟测试（/health + 401/403 鉴权验证）           │
└─────────────────────────────────────────────────────────┘
```

所有步骤幂等：多次运行 `configure.sh` 会覆盖 `values-prod.yaml` 与 Secret；`deploy-k8s.sh` 走 `helm upgrade --install`。

## 3. 一键部署（首次）

```bash
# 一、复制模板（此文件受 .gitignore 保护，不会提交）
cp deploy/deployment.config.example.yaml deployment.config.yaml
chmod 600 deployment.config.yaml

# 二、编辑占位符
#   必填：cluster / registry / ingress / mysql / redis / milvus host 等
#   详见 docs/CONFIGURATION.md
vim deployment.config.yaml

# 三、渲染本地工件（不访问集群）
./scripts/deploy/configure.sh --generate-secrets
#   - 自动填空的 Secret（JWT、API key、MinIO key、管理员初始密码）
#   - 校验强度 / 占位符完整度
#   - 生成 deploy/helm/sia/values-prod.yaml
#   - 生成 deploy/rendered/sia-secrets.yaml  (chmod 600)

# 四、真正部署
./scripts/deploy/deploy-k8s.sh
```

成功输出：

```
[OK] Helm deployment complete
[OK] Rollout complete
[OK]   health check 1/3: HTTP 200
[OK]   authz check:     HTTP 401 (expected 401/403 without credentials)
[OK] Smoke tests passed
```

## 4. 脚本参数

### 4.1 `configure.sh`
```
./scripts/deploy/configure.sh [options]

  -c, --config FILE         自定义配置文件路径（默认 ./deployment.config.yaml）
  --generate-secrets        为空 Secret 自动生成（随机 hex/base64，RSA keypair）
  --check-only              仅校验占位符，不写文件
```

### 4.2 `deploy-k8s.sh`
```
./scripts/deploy/deploy-k8s.sh [options]

  -c, --config FILE         配置文件（默认 ./deployment.config.yaml）
  -f, --values FILE         额外 Helm values 文件（叠加）
  -n, --namespace NS        覆盖命名空间
  -t, --tag TAG             镜像 tag（默认 git short SHA）
  --skip-build              不执行 docker build（CI 已推镜像时用）
  --skip-push               不 push 镜像
  --skip-smoke              不执行部署后冒烟
  --dry-run                 helm --dry-run
  --diff                    仅显示与当前 release 的差异
```

## 5. 典型场景

### 5.1 升级版本
```bash
# 改 deployment.config.yaml 中的镜像 tag (或通过 -t)
./scripts/deploy/deploy-k8s.sh -t v0.3.0 --skip-build --skip-push
# helm 滚动升级；迁移 Job 自动运行 alembic upgrade head
```

### 5.2 只轮换 Secret
```bash
# 在 deployment.config.yaml 里把要换的字段置空
./scripts/deploy/configure.sh --generate-secrets
kubectl apply -f deploy/rendered/sia-secrets.yaml
kubectl rollout restart deployment -n sia
```

### 5.3 CI 已构建镜像
```bash
./scripts/deploy/deploy-k8s.sh --skip-build --skip-push -t v0.2.0
```

### 5.4 Dry-run 对比
```bash
./scripts/deploy/deploy-k8s.sh --dry-run
# 或只看差异
./scripts/deploy/deploy-k8s.sh --diff
```

### 5.5 回滚
```bash
helm history  sia -n sia
helm rollback sia <revision> -n sia
```

## 6. TLS 到数据库

参考 [`CONFIGURATION.md`](./CONFIGURATION.md#tls) 中 `mysql.tls` / `redis.tls` 章节。核心步骤：

1. 从 DBA / 云控制台取 MySQL / Redis 的 CA 证书（PEM）
2. 在 `sia` 命名空间创建 Secret：
   ```bash
   kubectl -n sia create secret generic mysql-ca --from-file=ca.crt=./mysql-ca.pem
   kubectl -n sia create secret generic redis-ca --from-file=ca.crt=./redis-ca.pem
   ```
3. 在 `deployment.config.yaml`：
   ```yaml
   mysql:
     tls:
       mode: required
       caSecretName: mysql-ca
   redis:
     tls:
       enabled: true
       caSecretName: redis-ca
   ```
4. 重跑 `configure.sh && deploy-k8s.sh`

Helm 会把 CA 挂到 `/etc/sia/tls/mysql/ca.crt`、`/etc/sia/tls/redis/ca.crt`；应用通过 `SIA_MYSQL_TLS_CA_PATH` / `SIA_REDIS_TLS_CA_PATH` 读取。

## 7. 生产级 Secret 管理

`configure.sh` 生成的 `sia-secrets.yaml` 适合**初次部署**；生产环境强烈建议替换为以下之一：

### 7.1 [sealed-secrets](https://sealed-secrets.netlify.app/)
```bash
kubeseal --format yaml < deploy/rendered/sia-secrets.yaml \
  > deploy/sealed/sia-secrets.sealed.yaml
# 加密后的 SealedSecret 可安全提交到 Git
```

### 7.2 [External Secrets Operator](https://external-secrets.io/)
从 Vault / AWS Secrets Manager / Azure Key Vault / GCP Secret Manager 同步。示例：

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata: { name: sia-secrets, namespace: sia }
spec:
  refreshInterval: 1h
  secretStoreRef: { name: vault-backend, kind: ClusterSecretStore }
  target: { name: sia-secrets, creationPolicy: Owner }
  data:
    - secretKey: SIA_AUTH_JWT_SECRET
      remoteRef: { key: secret/sia/prod, property: jwt_secret }
    - secretKey: SIA_MYSQL_PASSWORD
      remoteRef: { key: secret/sia/prod, property: mysql_password }
    # ...
```

替换后，**不再用** `deploy/rendered/sia-secrets.yaml`；只要保证命名空间内有名为 `sia-secrets` 的 Secret 即可。

### 7.3 Vault Agent Injector
在 Pod 注解 `vault.hashicorp.com/agent-inject: "true"` 即可把 Vault 密钥注入到 Pod 文件系统，与 SIA 的 `SIA_SECRETS_DIR=/etc/sia/secrets` 约定一致。

## 8. Runbook（部署相关）

更完整的运维 Runbook 见 [`OPERATIONS_GUIDE.md`](./OPERATIONS_GUIDE.md)。部署阶段最常见的操作：

| 动作 | 命令 |
|---|---|
| 查看 release 状态 | `helm status sia -n sia` |
| 查看 Pod | `kubectl get po -n sia -o wide` |
| 查看迁移 Job 日志 | `kubectl logs -n sia job/sia-db-init-<rev>` |
| 进入 Pod 排障 | `kubectl exec -it -n sia <pod> -- /bin/sh` |
| 临时禁用 seed Job | `helm upgrade … --set jobs.seed.enabled=false` |

## 9. 不同部署方式对比

| 场景 | 命令 | 说明 |
|---|---|---|
| **首次全新部署** | `configure.sh --generate-secrets && deploy-k8s.sh` | 标准流程 |
| **升级到新版本** | `deploy-k8s.sh -t v0.x.y --skip-build --skip-push` | CI 已推镜像 |
| **本地镜像 + kind 验证** | `deploy-k8s.sh` （无 registry） | 镜像仅本地可用，Pod 需 `imagePullPolicy: Never` |
| **仅更新配置** | 编辑 `deployment.config.yaml` → `configure.sh` → `deploy-k8s.sh --skip-build --skip-push` | 重用已存在镜像 |
| **只看 diff** | `deploy-k8s.sh --diff` | 不修改集群 |
| **CI 自动化** | `.github/workflows/deploy.yml` | tag push 或手动 dispatch |

## 10. 首次部署后的 Checklist

部署完成后立刻核对：

- [ ] `kubectl get pods -n sia` —— 全部 Running
- [ ] `helm get values sia -n sia` —— 无占位符残留
- [ ] Ingress 证书已就绪：`kubectl describe ingress sia-ingress -n sia`
- [ ] 健康端点通过 Ingress 返回 200：`curl https://<INGRESS_HOST>/api/v1/health`
- [ ] 未鉴权访问返回 401：`curl -i https://<INGRESS_HOST>/api/v1/intelligence`
- [ ] Seed Job 已完成：`kubectl get job -n sia | grep seed`
- [ ] 可用初始 admin 账户登录并**立即修改密码**（初始密码在 `deployment.config.yaml` 的 `secrets.adminPassword`）
- [ ] `helm get manifest sia -n sia | grep -c 'readOnlyRootFilesystem: true'` ≥ 5
- [ ] 生产环境 `deployment.config.yaml` 已从磁盘移除或移入安全存储

完整安全基线见 [`SECURITY.md`](./SECURITY.md#部署验收-checklist)。

## 11. 常见部署问题

| 症状 | 原因 | 排查 |
|---|---|---|
| `configure.sh` 报 "required fields still contain placeholders" | 有未替换的 `<...>` | 按提示列表补齐 |
| Pod `CrashLoopBackOff` + `SIA_AUTH_JWT_SECRET is required` | Secret 未 apply 或未挂载 | `kubectl apply -f deploy/rendered/sia-secrets.yaml` + `rollout restart` |
| `Permission denied` 写 `/tmp` | emptyDir 未挂载 | 检查 `volumeMounts` 是否包含 `tmp` |
| MySQL TLS 握手失败 | CA Secret 缺失 / 路径不匹配 | `kubectl exec … -- ls /etc/sia/tls/mysql` |
| Trivy 扫描阻断 CI | 基础镜像有 HIGH CVE | 升级 `python:3.12-slim` 或 `nginxinc/nginx-unprivileged` 到新 patch |
| 冒烟测试 `authz check: HTTP 500` | API 启动异常 | `kubectl logs -n sia deploy/sia-api` |
| Helm stuck `pending-install` | 上次升级失败残留 | `helm history sia -n sia && helm rollback sia <rev>` |

---

*SIA v0.2.0 | Enterprise Deployment Guide*
