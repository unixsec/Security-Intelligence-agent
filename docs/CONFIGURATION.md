# 配置参考

SIA 的配置层次（优先级由高到低）：

1. **K8s Secret**（文件挂载到 `/etc/sia/secrets/*`）——「密」
2. **K8s ConfigMap**（以环境变量注入）——「非密」
3. **YAML 配置**（`config/auth.yaml` / `config/llm_gateway.yaml`）
4. **代码内默认值**（非生产）

生产环境必需的 Secret 缺失时应用**启动即崩溃**。

本文逐项列出占位符 / 环境变量 / Helm 值的语义、默认值、来源与安全等级。

---

## 1. `deployment.config.yaml` 占位符

### 1.1 必填（非密）

| 字段 | 示例 | 说明 |
|---|---|---|
| `cluster.context` | `prod-eu-west-1` | `kubectl config current-context` |
| `cluster.namespace` | `sia` | 目标命名空间（不存在会创建） |
| `registry.url` | `harbor.corp.com/sia` | 容器镜像注册表前缀 |
| `registry.pullSecret` | `harbor-pull-secret` | K8s `dockerconfigjson` Secret 名（匿名拉取留空） |
| `registry.buildLocally` | `true`/`false` | false 时 `deploy-k8s.sh` 跳过 build + push |
| `ingress.host` | `sia.company.com` | 公网域名 |
| `ingress.tls.secretName` | `sia-tls` | 现有 TLS Secret 名；若由 cert-manager 签发，填将被创建的名字 |
| `ingress.tls.clusterIssuer` | `letsencrypt-prod` | cert-manager `ClusterIssuer` |
| `mysql.host` | `rds-mysql.internal` | MySQL 端点 |
| `mysql.port` | `3306` | |
| `mysql.user` / `mysql.database` | `sia` / `sia` | |
| `mysql.tls.mode` | `disabled`\|`preferred`\|`required` | 推荐 `required` |
| `mysql.tls.caSecretName` | `mysql-ca` | K8s Secret，需含 `ca.crt` |
| `redis.host` / `redis.port` / `redis.db` | `redis.internal` / 6379 / 0 | |
| `redis.tls.enabled` | `true` | |
| `redis.tls.caSecretName` | `redis-ca` | |
| `milvus.host` / `milvus.port` | `milvus.internal` / 19530 | |
| `minio.enabled` | `true`/`false` | false 时可省 MinIO 全部字段 |
| `minio.host` / `minio.port` / `minio.bucket` / `minio.secure` | | `secure=true` 走 HTTPS |

### 1.2 必填（密 —— 可被 `configure.sh --generate-secrets` 自动生成）

| 字段 | 说明 | 自动生成？ |
|---|---|---|
| `secrets.jwtSecret` | HS256 签名密钥（≥ 32 hex） | ✅ `openssl rand -hex 32` |
| `secrets.jwtAlgorithm` | `HS256` \| `RS256`（生产推荐 `RS256`） | — |
| `secrets.jwtPrivateKey` / `jwtPublicKey` | RS256 PEM，base64 | ✅ 3072-bit RSA keypair |
| `secrets.apiKey` | `X-API-Key` 鉴权值 | ✅ |
| `secrets.adminPassword` | 初始 admin 密码（首次登录后必须改） | ✅ |
| `secrets.mysqlPassword` | MySQL 账号密码 | ❌ 必须人工提供（与外部 DB 一致） |
| `secrets.redisPassword` | Redis AUTH | ❌ 同上 |
| `secrets.minioAccessKey` / `minioSecretKey` | MinIO 凭据 | ✅ |
| `secrets.milvusToken` | Milvus 认证（若启用） | ❌ |
| `secrets.googleApiKey` | Gemini API key | ❌（留空即禁用 Gemini） |
| `secrets.anthropicApiKey` | Claude API key | ❌ 可选 |
| `secrets.openaiApiKey` | GPT API key | ❌ 可选 |

### 1.3 可选

| 字段 | 默认 | 说明 |
|---|---|---|
| `resources.api.replicas` | 2 | API 实例数（HPA 可拉伸） |
| `resources.consumer.replicas` | 1 | 消费者实例数 |
| `resources.web.replicas` | 2 | |
| `autoscaling.api.enabled` | true | |
| `autoscaling.api.minReplicas` / `maxReplicas` | 2 / 8 | |
| `autoscaling.api.targetCPUUtilizationPercentage` | 70 | |
| `network.httpsProxy` | "" | 企业出云代理（LLM API 用） |
| `network.egressAllowedCidrs` | `["0.0.0.0/0"]` | 出口 CIDR 白名单；严格环境收紧 |
| `observability.otlpEndpoint` | "" | OpenTelemetry Collector URL |
| `observability.logJsonFormat` | true | 结构化 JSON 日志 |
| `security.falcoRulesEnabled` | false | 部署 Falco 规则 ConfigMap |
| `security.gatekeeperConstraintsEnabled` | false | OPA Gatekeeper 示例（另见 `deploy/k8s/gatekeeper-constraints/`） |
| `jobs.migration.enabled` | true | post-install 运行 alembic |
| `jobs.seed.enabled` | true | 首次创建 admin + 默认源 + 评分策略（后续升级建议 false） |

---

## 2. 应用环境变量（由 Helm 注入，不要在生产手设）

| 变量 | 来源 | 说明 |
|---|---|---|
| `SIA_ENV` | ConfigMap | `production` \| `dev` \| `test` |
| `SIA_DEBUG` | ConfigMap | 生产强制 `false`，启动校验拒绝 true |
| `SIA_LOG_LEVEL` | ConfigMap | `INFO` \| `WARN` \| `ERROR` \| `DEBUG` |
| `SIA_LOG_JSON_FORMAT` | ConfigMap | 结构化 JSON 日志 |
| `SIA_API_HOST` / `SIA_API_PORT` | ConfigMap | `0.0.0.0:8080` |
| `SIA_CONFIG_DIR` / `SIA_PROMPTS_DIR` / `SIA_WORKFLOWS_DIR` | ConfigMap | 挂载路径 |
| `SIA_OTLP_ENDPOINT` | ConfigMap | 空则禁用 OTel 出口 |
| `SIA_MYSQL_*` | ConfigMap | host/port/user/database/pool_size/tls_mode/tls_ca_path |
| `SIA_MYSQL_PASSWORD` | **Secret**（文件挂载） | |
| `SIA_REDIS_*` | ConfigMap | host/port/db/tls_enabled/tls_ca_path |
| `SIA_REDIS_PASSWORD` | **Secret** | |
| `SIA_MILVUS_*` | ConfigMap | host/port/collection |
| `SIA_MILVUS_TOKEN` | **Secret** | |
| `SIA_MINIO_*` | ConfigMap | host/port/bucket/secure |
| `SIA_MINIO_ACCESS_KEY` / `SIA_MINIO_SECRET_KEY` | **Secret** | |
| `SIA_AUTH_JWT_ALGORITHM` | ConfigMap | `HS256` \| `RS256` |
| `SIA_AUTH_JWT_SECRET` | **Secret** | HS256 |
| `SIA_AUTH_JWT_PRIVATE_KEY` / `_PUBLIC_KEY` | **Secret** | RS256（base64 PEM） |
| `SIA_API_KEY` | **Secret** | |
| `SIA_ADMIN_PASSWORD` | **Secret** | 仅 seed job 使用 |
| `SIA_GOOGLE_API_KEY` / `SIA_ANTHROPIC_API_KEY` / `SIA_OPENAI_API_KEY` | **Secret** | LLM provider keys |
| `SIA_HTTPS_PROXY` | **Secret** | 企业出云代理 |
| `SIA_SECRETS_DIR` | 容器 env（固定） | `/etc/sia/secrets` |
| `HOME` / `HF_HOME` / `FONTCONFIG_PATH` | Deployment env | 读写指向 emptyDir，匹配 `readOnlyRootFilesystem` |

### 2.1 Secret 读取优先级（`sia/config.py`）

对每个 Secret 字段：

1. Pydantic 默认（代码内，通常为空串）
2. 环境变量 `SIA_XXX`
3. **文件** `/etc/sia/secrets/SIA_XXX`（优先级最高）

生产环境推荐只走文件挂载，避免 env 出现在 `kubectl describe pod` / ps / 日志里。

---

## 3. YAML 配置文件

### 3.1 `config/auth.yaml`

```yaml
jwt:
  secret_key: "${SIA_AUTH_JWT_SECRET}"    # 必填（HS256）
  algorithm:  "${SIA_AUTH_JWT_ALGORITHM:-HS256}"
  private_key: "${SIA_AUTH_JWT_PRIVATE_KEY}"   # 仅 RS256
  public_key:  "${SIA_AUTH_JWT_PUBLIC_KEY}"    # 仅 RS256
  access_token_expire_minutes: 30
  refresh_token_expire_days: 7

lockout:
  max_failed_attempts: 5
  lockout_duration_minutes: 30

password:
  min_length: 8
  require_uppercase: true
  require_lowercase: true
  require_digit: true
  require_special: false

oidc:
  enabled: false
  providers:
    # 启用示例（Azure AD / Keycloak）见注释

ldap:
  enabled: false
  # 企业 AD 集成示例见注释

api_key:
  enabled: true
  header_name: "X-API-Key"
```

**修改不需要重启**：应用在下次请求时重新读取 `get_auth_config()`（`@lru_cache` 需重启才生效；可用 `kubectl rollout restart`）。

### 3.2 `config/llm_gateway.yaml`

LLM 路由、超时、熔断、脱敏规则。关键段落：

```yaml
default_model: gemini-pro

models:
  gemini-pro:
    provider: google
    api_key_env: SIA_GOOGLE_API_KEY
    timeout_sec: 60
    max_tokens: 8192
  claude-sonnet:
    provider: anthropic
    api_key_env: SIA_ANTHROPIC_API_KEY
  deepseek-r1:          # 本地 OpenAI 兼容
    provider: local_openai_compat
    base_url: http://llm-gateway.internal/v1
    api_key_env: SIA_LLM_LOCAL_KEY

circuit_breaker:
  failure_threshold: 5
  recovery_timeout_sec: 60

failover:
  analyze_intel:  [gemini-pro, claude-sonnet, deepseek-r1]

anonymization:
  enabled_for_cloud: true
  patterns:
    - name: internal_ip
      regex: "\\b10\\.\\d+\\.\\d+\\.\\d+\\b"
      replacement: "<REDACTED_IP_{n}>"
    - name: employee_name
      regex_file: /etc/sia/secrets/employee_names.txt
      replacement: "<REDACTED_EMPLOYEE_{n}>"
```

---

## 4. Helm values 层级

```
values.yaml                      (默认)
   ↓ 覆盖
values-prod.yaml                 (由 configure.sh 生成，gitignored)
   ↓ 覆盖
helm upgrade --set ...           (一次性覆盖，尽量避免)
```

只有 `global.imageRegistry`、`api/consumer/web.image.tag`、`namespace` 需要在 `deploy-k8s.sh` 里 `--set` 覆盖，因它们依赖 git SHA 或 CLI 参数。

---

## 5. 配置相关安全规则

1. **deployment.config.yaml 永远不提交** —— 已在 `.gitignore`
2. **rendered/sia-secrets.yaml 永远不提交** —— 已在 `.gitignore`，本地文件模式 600
3. **禁用默认值**：生产环境如果检测到 `SIA_AUTH_JWT_SECRET in ("change-me-in-production", "changeme", "secret")`、MinIO `minioadmin:minioadmin` 等，应用启动崩溃
4. **Secret 只读文件挂载**：`defaultMode: 0400`
5. **弱密码拒绝**：`configure.sh` 会拒绝 `password / admin / 123456 / letmein / changeme / sia / test`
6. **JWT HS256 最短 32 字节**
7. **密码不在 allow list**：`.claude/settings.local.json` 不应包含任何命令中嵌入的凭据

---

## 6. 配置变更流程

日常调优非敏感参数：

```bash
$EDITOR deployment.config.yaml           # 调 resources / autoscaling / egressCidrs 等
./scripts/deploy/configure.sh            # 重新渲染 values-prod.yaml
./scripts/deploy/deploy-k8s.sh --skip-build --skip-push   # 只跑 helm upgrade
```

轮换 Secret：

```bash
# 方式 1：configure.sh 重生成（合适仅管理员掌握密钥时）
$EDITOR deployment.config.yaml           # 清空要轮换的字段
./scripts/deploy/configure.sh --generate-secrets
kubectl apply -f deploy/rendered/sia-secrets.yaml
kubectl rollout restart deployment -n sia

# 方式 2：外部 Secret manager（推荐）
# 在 Vault/External Secrets 里更新源值，等待下次同步即可
```

---

*SIA v0.2.0 | Configuration Reference*
