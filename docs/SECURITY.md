# 安全模型

面向企业安全审计、合规、红/蓝队评估。涵盖威胁模型、加固基线、应急响应、漏洞披露流程。

## 1. 威胁模型（STRIDE）

| 类别 | 典型威胁 | SIA 中的控制 |
|---|---|---|
| **S**poofing | 伪造用户身份 | JWT（RS256 推荐）+ LDAP/OIDC；API-Key 仅用于 server-to-server |
| **T**ampering | 修改情报 / 报告 / 审计 | 读 API 要求 viewer 角色，写 API 要求 analyst+，审计日志单独 logger |
| **R**epudiation | 用户抵赖 | 结构化审计日志（`sia.audit`）落 MySQL + 日志管道，带 ts/actor/ip/ua |
| **I**nformation disclosure | Secret 泄露、出云 LLM 泄敏 | Secret 仅文件挂载；出云前正则 + 白名单脱敏；日志 redaction |
| **D**enial of Service | 暴破、请求洪水 | 分层限流：默认 30 req/min/身份 + 登录 5 req/min/IP；HPA |
| **E**levation of Privilege | 绕过 RBAC、容器逃逸 | FastAPI `Depends(require_role(...))`；容器 `readOnlyRootFilesystem` + `drop: [ALL]` + `seccomp RuntimeDefault` |

## 2. 加固基线（20 项）

部署后按 [`DEPLOYMENT_GUIDE.md` §10 Checklist](./DEPLOYMENT_GUIDE.md#10-首次部署后的-checklist) 验收。

### Critical / High

| ID | 要求 | 实现 | 如何验证 |
|---|---|---|---|
| SEC-001 | 无默认 JWT 密钥 | `AuthSecretSettings` 生产环境校验；占位符如 `change-me-in-production` 触发崩溃 | 临时不设 `SIA_AUTH_JWT_SECRET` 启动，应见 `RuntimeError` |
| SEC-002 | 无默认数据库密码 | `DatabaseSettings.password` 默认空串，生产强制 | 同上 |
| SEC-003 | 无默认 MinIO 凭据 | `MinIOSettings` 拒绝 `minioadmin:minioadmin` | 同上 |
| SEC-005 | API Key 不 log | `rbac.py` 常数时间比较 + redaction filter | grep 日志无 X-API-Key 值 |

### Medium

| ID | 要求 | 实现 |
|---|---|---|
| SEC-004 | 生产禁 debug | `Settings._validate_env()` 拒绝 `env=production` + `debug=true` |
| SEC-006 | 按身份限流 | `RateLimitMiddleware` 优先用 JWT digest / API-key digest / IP |
| SEC-007 | 到 DB/Redis TLS | `DatabaseSettings.tls_mode`, `RedisSettings.tls_enabled`；Helm 挂 CA Secret 到 `/etc/sia/tls/` |
| SEC-008 | Secret 作为文件 | `SIA_SECRETS_DIR=/etc/sia/secrets`；Secret 挂 `defaultMode: 0400`，envFrom 不再使用 |
| SEC-009 | 容器加固 | 所有 Pod: `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `drop: [ALL]`, `seccompProfile: RuntimeDefault` |
| SEC-010 | nginx 非 root | `nginxinc/nginx-unprivileged` 基镜像，UID 101，监听 8080 |
| SEC-011 | 镜像供应链 | CI 走 Trivy（HIGH+ 阻断）+ Syft SBOM + Cosign keyless 签名 |
| SEC-012 | 集群级防护 | 可选 Falco 规则 ConfigMap；可选 OPA Gatekeeper 约束（`deploy/k8s/gatekeeper-constraints/`） |
| SEC-013 | 审计 | `sia.common.audit.audit()` 结构化 JSON，login/失败/敏感操作必调 |
| SEC-014 | 推荐 RS256 | `jwtAlgorithm: RS256` + 3072-bit 密钥对（configure.sh --generate-secrets 自动生成） |
| SEC-015 | 登录独立限流 | RateLimitMiddleware: 5 req/min/IP 针对 `/api/v1/auth/login` / `/auth/oidc` / `/auth/ldap` |

### Low

| ID | 要求 | 实现 |
|---|---|---|
| SEC-016 | 日志脱敏 | `sia.common.logging_redact.install_redaction()` 挂根 logger + sqlalchemy/httpx |
| SEC-017 | 依赖更新 | `.github/dependabot.yml` 周扫 pip/npm/docker/actions；CI 含 `pip-audit` |
| SEC-018 | 消费者优雅退出 | `run_analysis_consumer` 捕 SIGTERM / SIGINT，完成当前消息后停 |
| SEC-019 | 跨节点散布 | 所有 Deployment 带 `topologySpreadConstraints` (hostname + zone) |
| SEC-020 | 出口 CIDR | `network.egressAllowedCidrs` 可收紧至企业内网 |

## 3. 密钥分级

| 等级 | 例子 | 处置 |
|---|---|---|
| P0（高危） | JWT 私钥 / API Key / DB root 密码 | Vault / External Secrets；**永不**出现在日志、values.yaml、CI 输出、聊天 |
| P1 | MinIO / Milvus / LLM provider key | 同上；LLM key 建议按场景分 key（分析 / 报告 / 开发） |
| P2（非密） | DB host、bucket 名、域名 | 可进 ConfigMap 和 Git |

**任何 P0/P1 进入 Git = 立即轮换**，即使是 commit --amend 或 git filter-repo 之后——假设已泄露。

## 4. 默认拒绝

| 入口 | 默认策略 |
|---|---|
| API（缺鉴权） | `401 Authentication required` |
| RBAC（角色不足） | `403 Requires role '...' or above` |
| CORS（生产） | `allow_origins: []`（前端与 API 同源走 Ingress，不需要 CORS） |
| NetworkPolicy | Ingress/Egress 默认拒绝，白名单放行 DNS / MySQL / Redis / Milvus / MinIO / 443 / 80 |
| 容器能力 | `drop: [ALL]`，不加任何 CAP |
| 文件系统 | `readOnlyRootFilesystem: true` |

## 5. 机密处理路径

```
Secret source (Vault / External Secrets / sealed-secrets / 手工)
    │
    ▼
K8s Secret  sia-secrets      (namespace: sia)
    │
    │  mounted as files, mode 0400
    ▼
Pod filesystem  /etc/sia/secrets/*
    │
    │  read by AuthSecretSettings / DatabaseSettings / ...
    ▼
Application  (in-memory only)
```

**不走**：
- 环境变量（避免 `env` / `kubectl describe pod` 泄露）
- values.yaml（避免 Git 历史）
- --set CLI 参数（避免 shell history / CI 日志）
- 命令行日志（redaction filter 会二次拦截）

## 6. 审计事件清单

已接入 `audit()` 的事件：

| event | 触发点 | 关键字段 |
|---|---|---|
| `user.login` | `/api/v1/auth/login` | actor_id, actor_name, result (success/failure), reason, provider, ip |
| *（待补）* | 管理员操作、报告导出、源配置变更 | 建议按 `admin.<resource>.<action>` 命名 |

> **开发约定**：任何"有后果"的 POST/PUT/DELETE 在 handler 首尾调用 `audit()`。返回前 log，无论成功失败。

## 7. 容器逃逸防线

按层倒序：

1. 应用代码：输入校验（pydantic），SQL 绑定参数，无命令拼接
2. 镜像：多阶段构建，运行时无编译工具
3. 运行时：`readOnlyRootFilesystem` + `drop: [ALL]` + `seccompProfile`
4. Namespace：NetworkPolicy 限制出口
5. 集群：OPA Gatekeeper 拒绝 `privileged: true`、`:latest` tag
6. 主机：Falco 运行时检测（shell spawn、/etc 写、异常 egress）

## 8. 应急响应

### 8.1 怀疑 Secret 泄露
```bash
# 1. 立即轮换所有 Secret
$EDITOR deployment.config.yaml    # 清空 jwtSecret/apiKey/adminPassword/...
./scripts/deploy/configure.sh --generate-secrets
kubectl apply -f deploy/rendered/sia-secrets.yaml
kubectl rollout restart deployment -n sia

# 2. 撤销外部 API key（Gemini / OpenAI 控制台）
# 3. 吊销现存所有 refresh token
kubectl -n sia exec deploy/sia-api -- python -c \
  "from sia.models.user import RefreshToken; ..."    # 按运维操作手册

# 4. 审计日志：导出最近 7 天 sia.audit 全量，交安全团队
```

### 8.2 可疑账户行为
1. 立即锁定：`UPDATE user SET status='locked' WHERE id=?`
2. 导出该用户近 30 天审计：`{actor_id=?}` 日志过滤
3. 检查 refresh_token 表，撤销相关 token_hash

### 8.3 供应链问题（CVE 爆发）
```bash
# 当天评估
trivy image <REGISTRY>/sia-backend:<current-tag> --severity HIGH,CRITICAL

# 24h 内出热修分支：升级受影响包，CI 全流程过
# 镜像签名 + 部署
./scripts/deploy/deploy-k8s.sh -t v0.2.1-hotfix
```

### 8.4 恶意情报源（可能引起 LLM 越狱 / Prompt Injection）
SIA 的 LLM 调用在 `gateway/llm/` 统一经过：
- 输入：情报正文仅作为 `user` 角色消息传入；系统提示词独立保存在 `prompts/` 挂载为只读
- 输出：JSON schema 校验（`pydantic`），失败不入库
- 出云脱敏：见 `llm_gateway.yaml` `anonymization`

若检测到异常模式（例如 LLM 返回格式整块被改写），临时措施：
```bash
# 切换到更严格的本地模型
$EDITOR config/llm_gateway.yaml   # default_model → deepseek-r1
kubectl -n sia rollout restart deployment
```

## 9. 合规快照

SIA 的设计对应常见合规条款：

| 要求 | 映射 |
|---|---|
| 等保 2.0 "身份鉴别" | JWT + LDAP + OIDC + 账号锁定 |
| ISO 27001 A.12.4 "日志记录" | `sia.audit` 结构化日志 + 只进不出 logger |
| GDPR Art. 32 "加密传输与存储" | Ingress TLS；DB/Redis TLS；Secret 文件挂载 |
| SOC 2 "最小权限" | 容器 `drop: [ALL]`、RBAC 三级角色、NetworkPolicy |
| PCI-DSS 6.5 "常见编码缺陷" | SQL 参数绑定；输入 pydantic；输出 redaction |

（以上是映射示例；实际合规认证由审计机构依据证据判定。）

## 10. 漏洞披露

对外报告漏洞建议渠道：

- 邮件：`unix_sec@163.com`
- 响应 SLA：72 小时回复、30 天内修复 / 给出缓解
- 鼓励：感谢信或漏洞奖金（由部署方决定）

**请勿**在公开 Issue 披露未修复的漏洞。

## 11. 生产部署加固清单（Production Hardening Checklist）

> v0.2.0 是 **Early Access**。在面向生产部署前**必须**完成以下检查项。Task ID 与详细决策（含 ADR / NFR / FMEA）由维护者在本地 `design/` 目录管理，该目录不上传 GitHub。

### 11.1 强制项（阻断生产）

| # | 检查项 | 验证命令 | 关联 Task |
|---|---|---|---|
| 1 | LDAP 过滤器已转义元字符 | `grep "escape_filter_chars" src/sia/auth/providers/ldap.py` | SEC-1 |
| 2 | API Key 已支持 scope/role | `kubectl get secret sia-api-keys -o yaml \| grep role` | SEC-2 |
| 3 | OIDC 启用 PKCE | `grep "code_challenge" src/sia/auth/providers/oidc.py` | SEC-3 |
| 4 | JWT 撤销机制可用 | `curl -X POST /api/v1/auth/logout` 后旧 token 应 401 | SEC-4 |
| 5 | DNS 解析有超时 | `grep "_DNS_TIMEOUT" src/sia/collector/url_validator.py` | SEC-5 |
| 6 | Helm `ingress.tls.enabled=true` | `helm get values sia \| grep "tls:" -A1` | DEP-1 |
| 7 | egressAllowedCidrs 收窄到允许列表 | values.yaml 不含 `0.0.0.0/0` | DEP-1 |
| 8 | Gatekeeper 约束已自动应用 | `kubectl get constraints` 应有 5+ 项 | DEP-2 |
| 9 | alembic versions 目录非空 | `ls migrations/versions/*.py` | DEP-4 |
| 10 | 所有强密钥从外部 Secret 读取 | `kubectl get secret sia-secrets` | （已实现） |
| 11 | Trivy 镜像扫描在 CI 阻塞 | `.github/workflows/ci.yml` 含 `exit-code: '1'` | （已实现） |
| 12 | pip-audit 在 CI 阻塞 | CI yaml 中无 `\|\| true` | TEST-2 |

### 11.2 强烈建议项

| # | 检查项 | 关联 Task |
|---|---|---|
| 13 | /metrics 端点开放并被 Prometheus 抓取 | OBS-1 |
| 14 | 限速器使用 Redis（多副本一致） | FN-4 |
| 15 | 至少 1 条 E2E 测试在 CI 跑通 | TEST-1 |
| 16 | Pod Security Standards labels 应用到 namespace | DEP-3 |
| 17 | Falco runtime 检测启用 | （集群侧 operator 部署） |
| 18 | 备份恢复演练（dr_drill.sh）每季度 1 次 | （运维 SOP） |
| 19 | OpenTelemetry tracing 接入 | OBS-2 |
| 20 | 渗透测试 + bug bounty | （外部） |

### 11.3 部署前一键自检脚本

```bash
# 在仓库根目录运行
bash scripts/ops/preflight_check.sh
```

预期：所有 P0 项 ✓ ；任何 ✗ 项必须修复后再部署生产。脚本本身在 v0.3 落地（见 IMPROVEMENT_PLAN）。

## 12. 漏洞披露与 Bug Bounty 流程（v0.4）

### 12.1 报告渠道

| 渠道 | 用途 |
|---|---|
| `unix_sec@163.com` (主) | 所有漏洞披露，PGP 密钥见 `/.well-known/security.txt` |
| GitHub Security Advisories | 仅当报告者明确希望走 GitHub 流程 |
| 公开 Issue | **禁止**披露未修复的漏洞 |

### 12.2 范围（Scope）

**In scope**（接受报告并支付奖金，奖金由部署方设置；本仓库不直接发奖）：

- `src/sia/**` — 所有应用代码
- `deploy/helm/sia/**` — Helm chart 安全配置缺陷
- `deploy/docker/**` — 容器逃逸 / 镜像加固
- `scripts/deploy/configure.sh`, `scripts/deploy/deploy-k8s.sh` — 部署脚本注入或权限问题
- `web/**` — 前端 XSS / CSRF / 注入

**Out of scope**：

- 第三方依赖的已知 CVE（请向上游报告；本项目通过 pip-audit / Trivy 跟踪）
- 用户配置错误造成的暴露（如 0.0.0.0/0 ingress）
- DOS / 暴力破解（已通过限速器缓解）
- 未实现的功能（如 Webhook 通用插件之外的渠道）
- 仅在 dev/test 模式生效的 backdoor（如 anonymous role，prod 强校验已禁）

### 12.3 严重度评估（CVSS 3.1 + 业务上下文）

| 严重度 | CVSS | SLA 修复 | 示例 |
|---|---|---|---|
| Critical | 9.0+ | 7 天 | RCE，认证完全绕过，密钥泄露 |
| High | 7.0–8.9 | 30 天 | 权限提升，SQLi，已知 IOC 数据泄露 |
| Medium | 4.0–6.9 | 90 天 | XSS，限速绕过，CSRF（非关键路径） |
| Low | < 4.0 | best-effort | 信息泄露（Server header），日志冗余 |

### 12.4 处理流程

```
报告者 → 我们 (72h ack) → 评估严重度 → 私下修复 PR (针对私有 CVE 分支)
  → 协调披露日期 (默认 90 天，或受影响用户 75% 已升级)
  → CVE 申请 + 公开 advisory + CHANGELOG 致谢
```

### 12.5 渗透测试节奏

| 类型 | 频率 | 范围 |
|---|---|---|
| 内部红队 | 季度 1 次 | 完整 K8s 部署 + chaos drill |
| 外部黑盒 | 年度 1 次 | API + 前端 + 部署链 |
| SAST + SCA | 每次 PR | Trivy + pip-audit + ruff security rules |
| DAST | 周 | 内部 staging（OWASP ZAP / Nuclei） |

外部测试报告由维护者在本地 `design/` 目录归档（该目录整体不上传 GitHub）；摘要 + 已修复结论入本节末尾的"历史"表。

### 12.6 .well-known/security.txt

公开部署应在 ingress 暴露：

```
Contact: mailto:security@<your-domain>
Expires: 2027-01-01T00:00:00Z
Encryption: https://<your-domain>/.well-known/pgp-key.asc
Acknowledgments: https://<your-domain>/security/credits
Preferred-Languages: en, zh
Canonical: https://<your-domain>/.well-known/security.txt
Policy: https://<your-domain>/security/policy
```

参考 RFC 9116。模板见仓库根的 `.well-known/security.txt.example`。

### 12.7 历史（每次修复后追加）

| 报告日期 | CVE | 严重度 | 状态 | 致谢 |
|---|---|---|---|---|
| — | — | — | — | — |

---

*SIA v0.4 | Security Model & Hardening Baseline (with §11 production checklist + §12 vulnerability disclosure)*
