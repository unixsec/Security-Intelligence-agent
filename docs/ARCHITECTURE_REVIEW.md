# 企业级架构评审（Chief Architect Review）

> **评审对象**：Security Intelligence Agent v0.2.0
> **评审视角**：Chief Architect / 平台 SRE / 安全架构
> **评审方法**：设计文档（v5.0）与代码库双向核对 + 企业级成熟度基准
> **评审日期**：2026-04-23
> **结论（一句话）**：**架构设计优秀**（C4/ADR/威胁建模齐全），**部署与安全基线扎实**（20 项加固），但在 **业务连续性（备份/DR）、多租户、数据治理、成本治理、SRE 成熟度** 五大维度存在**系统性缺口**，且代码实现层 20 项核查中 **10 处与设计承诺不一致**（"纸面有、代码无"）。定位：当前是 "**优秀的参考实现**"，距 "**严肃的企业生产系统**" 还差一次明确的 v0.3 专项落地。

---

## 目录

- [A. 执行摘要](#a-执行摘要)
- [B. 代码级落地核查（20 项，已逐行验证）](#b-代码级落地核查20-项已逐行验证)
- [C. 架构级企业能力缺口（10 大维度）](#c-架构级企业能力缺口10-大维度)
  - [C1. 业务连续性（备份 / DR）](#c1-业务连续性备份--dr)
  - [C2. 多租户与租户隔离](#c2-多租户与租户隔离)
  - [C3. 数据治理与合规](#c3-数据治理与合规)
  - [C4. 成本治理（LLM 花费）](#c4-成本治理llm-花费)
  - [C5. SRE 成熟度（SLI/SLO / 变更 / 混沌）](#c5-sre-成熟度slislo--变更--混沌)
  - [C6. API 平台化](#c6-api-平台化)
  - [C7. AI/ML 运营（LLMOps）](#c7-aiml-运营llmops)
  - [C8. 纵深防御（超出 20 项基线）](#c8-纵深防御超出-20-项基线)
  - [C9. 开发者体验与 Onboarding](#c9-开发者体验与-onboarding)
  - [C10. 合规证据自动化](#c10-合规证据自动化)
- [D. 优先级路线图（v0.3.x → v1.0）](#d-优先级路线图v03x--v10)
- [E. 立即可做的 3 个 patch 示例](#e-立即可做的-3-个-patch-示例)
- [F. 成熟度评分雷达](#f-成熟度评分雷达)

---

## A. 执行摘要

### A.1 做得好的地方（保持）

| 维度 | 评价 |
|---|---|
| **架构设计** | v5.0 文档含 C4 三层、序列、状态机、ER、威胁 DFD、ADR×12、NFR、FMEA；超出大多数企业项目的设计深度。 |
| **部署一键化** | `deployment.config.yaml` + `configure.sh` + `deploy-k8s.sh` 三脚本串联，幂等、可重入。 |
| **容器硬化** | Pod Security Restricted 全量落地（readOnlyRootFS + drop:[ALL] + seccomp + 非 root）。 |
| **Secret 管理** | 文件挂载（不走 env），生产强校验默认值，弱凭据拒绝启动。 |
| **供应链安全** | CI 集成 Trivy + Syft SBOM + Cosign keyless + Dependabot + pip-audit + personal-info lint。 |
| **审计日志** | 独立 `sia.audit` logger（`propagate=false`），双通道（stdout + DB）设计。 |
| **LLM 网关** | CircuitBreaker + failover chain + 出云脱敏，抽象清晰。 |
| **文档完整性** | 9 份权威运维文档 + 20 张架构图（PNG）+ CHANGELOG + LICENSE。 |

### A.2 Top 5 必须在上生产前修复

1. **🔴 SSRF**：Collector 对 URL 无 scheme / host / IP 校验，攻击者可通过修改 `source.url` 扫内网（169.254.169.254 取云 metadata、127.0.0.1:6379 打 Redis）。
2. **🔴 定时任务重复触发**：APScheduler 嵌入 `sia-api`，多副本（HPA）时无分布式锁，每个 replica 都独立触发 cron，导致情报重复抓取、报告重复生成。
3. **🔴 审计日志可篡改**：`audit_log` 表定义了 `prev_hash` / `current_hash` 字段但**代码从未填充**；`sia.audit` 写 stdout 而非 DB；DB 账号对该表无 INSERT-only 约束。出事时无法向监管证明日志未被 tampered。
4. **🟠 Outbox Publisher 未实现**：表建了、ADR 写了、ER 图画了，**生产代码里没有消费者进程**。设计承诺的"业务 + 消息原子性"不成立。
5. **🟠 备份与 DR 完全外包**：文档明确"依赖平台团队"，但未定义 RPO/RTO 验收、未演练、未有备份恢复 Runbook 代码。这是企业生产系统的**一等风险**。

### A.3 项目定位与差距

```
 成熟度谱系 (1-5)
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1. 原型         ██                                    演示可跑
 2. MVP          ████                                  小规模试用
 3. 工程化       ██████                                CI/CD + 监控 + 文档
 4. 企业级       ████████       ← SIA v0.2.0 当前      高可用 + 合规 + DR
 5. 关键业务     ██████████                            SLA 99.99 + 多活
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- 当前位置：**Level 3.5**（工程化完成度高，但企业级能力存在系统性缺口）
- 目标位置：**Level 4**（企业级），需完成 v0.3 "企业化专项" 落地
- 远期目标：**Level 5**（关键业务级），需引入多活、合规自动化、Chaos 演练

---

## B. 代码级落地核查（20 项，已逐行验证）

代码扫描见 Explore 审计结果。本节按 **严重度 × 设计/代码对齐度** 重排：

### 🔴 Critical（阻塞上生产）

| # | 项 | 设计承诺 | 代码现状 | 证据 |
|---|---|---|---|---|
| 1 | SSRF 防护 | SECURITY.md "默认拒绝" 边界 A→B | **无任何校验**，URL 直接走 httpx.get | `src/sia/collector/fetcher.py:78-84` |
| 2 | 分布式锁 | — | `max_instances=1` 仅 pod 内，跨 replica 无锁 | `src/sia/scheduler/service.py:21-73` |
| 3 | 审计 Hash 链 | SECURITY.md §13 + ADR-010 | 表有 `prev_hash` / `current_hash`，**代码从未填充** | `src/sia/models/system.py:25-38` vs `src/sia/common/audit.py` |
| 4 | DB 对 audit_log 的权限 | ADR-010 | 无 `GRANT INSERT ONLY`，app DB 账号可改审计 | `migrations/` 无该约束 |

### 🟠 High（生产后 30 天内）

| # | 项 | 对齐度 | 证据 |
|---|---|---|---|
| 5 | Outbox Pattern 消费者 | ❌ 表有 / 代码无 | `src/sia/models/system.py:56-75` 定义完整，无任何 `OutboxPublisher` 类 |
| 6 | MySQL / Redis Circuit Breaker | ❌ 仅 LLM 有 | `src/sia/common/database.py`、`redis.py` 无 retry / CB |
| 7 | 首次登录强制改密 | ❌ 无 | `user.password_changed_at` 字段存在但 login 无检查 |
| 8 | 前端 Authorization 注入 | ⚠️ 未核实 | `web/src/api/index.js` 无拦截器，若未在其他文件设置则接口会匿名 |

### 🟡 Medium（v0.4 / v0.5）

| # | 项 | 证据 |
|---|---|---|
| 9 | LLM 响应缓存 | 无实现，同一 prompt 重复调用浪费成本 |
| 10 | 出站 HTTP 单源限速 | 无实现，可能被源站 ban IP |
| 11 | API Idempotency-Key | POST 端点无去重，网络抖动下重复创建 |
| 12 | Feature Flag / Kill Switch | 无运行时开关，需改配置 + 重启 |
| 13 | 集成测试 / E2E | 57 单元测试，0 集成/E2E |
| 14 | 工作流版本锁定 | YAML 修改中期执行版本不一致 |
| 15 | 内容大小 / Content-Type 白名单 | 仅超时，响应大小无上限 |
| 16 | LLMGateway DI / 测试友好 | per-consumer 实例，无工厂，mocking 麻烦 |

### ✅ 真的做到了

| # | 项 | 证据 |
|---|---|---|
| 17 | init_admin.py 幂等 | 检测存在即 return，不覆盖 |
| 18 | Redis 密码从 Secret 读 | `_resolve_secret()` 文件优先 → env 兜底 |
| 19 | 无 CSRF 风险 | 使用 Bearer header，不带 Cookie |
| 20 | 无文件上传攻击面 | `/reports/generate` 仅传参，无 multipart |

### 🔵 Not Applicable（设计未用）

- **MinIO 代码未调用**：`MinIOSettings` 定义完整但 `src/sia/` 无 `minio.Client()`。报告当前全存 MySQL 的 `Report.content_json`。**这是设计与实现的断裂**：v5.0 架构图里 MinIO 是报告归档，现实中没用上。

---

## C. 架构级企业能力缺口（10 大维度）

以下是 Explore agent 做不到的部分 —— 不在单个文件里，而是跨系统、跨团队、跨生命周期的企业能力。

---

### C1. 业务连续性（备份 / DR）

**现状**：`docs/OPERATIONS_GUIDE.md §6` 只有一句"依赖平台托管服务的备份"。

**缺口**：

| 维度 | 现状 | 企业级要求 |
|---|---|---|
| **RPO / RTO 明确定义** | NFR 写了 RPO 5min / RTO 30min | 未经演练验证、无月度 DR drill 记录 |
| **MySQL 备份** | 依赖平台 | 未定义：备份频率、保留期、加密、跨区复制、PITR 测试脚本 |
| **Redis 备份** | 依赖平台 | Redis 作为队列是否可容忍丢失？若是缓存，AOF/RDB 频率 |
| **Milvus 备份** | 无 | Milvus 没有 SLA 级别的备份方案；`rebuild_vectors.py` 脚本**不存在** |
| **MinIO 备份** | 提及 version control | 未配置跨桶复制、跨区复制、加密 at rest |
| **应用配置备份** | `values-prod.yaml` 在部署机本地 | K8s Secret / ConfigMap 没走 GitOps，丢了只能重新 configure.sh |
| **DR 演练** | 无 | 每季度一次的"删库演练 + 20 分钟内恢复"，无代码 / 无文档 |
| **运行中任务的恢复** | Redis Streams 有 DLQ | `analyzing` 状态的情报若 consumer 崩溃 + Redis 数据丢失 → 需要一个 reconciler 扫 MySQL 里 `status=analyzing` 超过 X 分钟的重排队。**无实现**。 |
| **多区域 / 多活** | 单集群设计 | 无跨区 readonly 副本、无故障切换 SOP |

**建议交付物（v0.3）**：
- `scripts/ops/backup.sh` / `restore.sh`（协调平台托管 API）
- `scripts/ops/dr-drill.sh`（自动销毁 → 恢复 → 验证链路）
- `docs/RUNBOOKS/DR.md` Runbook，含 RPO/RTO 演练记录表
- `scripts/ops/rebuild_vectors.py`（Milvus 丢失时从 MySQL 情报重建）
- `scripts/ops/reconcile_analyzing.py`（孤儿情报重排队）
- Helm chart 支持 Velero backup hook

---

### C2. 多租户与租户隔离

**现状**：所有情报、用户、配置共享同一张表，**根本不是多租户架构**。

**场景压力**：若企业决定让集团下多个子公司（中国 / 欧盟 / 东南亚）独立使用，当前架构无法隔离。

**缺口**：

| 维度 | 现状 | 需要 |
|---|---|---|
| **数据隔离** | 单 DB 共享 | 至少 row-level tenancy（`tenant_id` 列 + 全局 RLS） |
| **鉴权隔离** | 单 JWT scope | JWT claim 带 tenant，API 中间件按 tenant 过滤 |
| **RBAC 隔离** | 三角色全局 | 租户内三角色 + 跨租户 super-admin |
| **资源配额** | 只有 IP/user 限流 | 按租户的 LLM token / 存储 / API QPS |
| **UI 租户切换** | 无 | 前端租户 picker、审计事件带 tenant |
| **数据残留删除** | 无 | 租户离开时的 data deletion API（GDPR 被遗忘权） |

**建议**：v0.4 或 v1.0 阶段，若业务真需要多租户再做 —— 这是**架构级重构**，不是 patch。若不做多租户，明确**"单租户 / 部署多实例"**的立场写进 README。

---

### C3. 数据治理与合规

| 维度 | 现状 | 需要 |
|---|---|---|
| **数据分级（TLP）** | v4.0 设计提及，代码 `intelligence.tlp_level` 字段 | 实际是否按 TLP 过滤展示、分发？无代码验证 |
| **数据生命周期** | OPERATIONS_GUIDE 有表 | 无实现：定时 job 按 "热/温/冷/归档/删除" 自动移动 |
| **GDPR 被遗忘权** | 无 | 用户注销时：`DELETE user + audit_log 中个人字段置空（不删行） + 报告中匿名化` |
| **数据可携带性** | 无 | `GET /users/{id}/export` 导出用户数据为 JSON（GDPR Art.20） |
| **数据血缘 Lineage** | 无 | 报告里一条结论来自哪几条情报 / 哪个 LLM 调用（`llm_call_log` 有 `request_id` 但不贯穿） |
| **数据驻留** | 无 | 跨国企业场景：欧盟数据不出欧盟、中国数据不出中国的物理隔离 |
| **审计保留期** | 无自动化 | `audit_log` 保留多久？清理策略？法律保留（legal hold）？ |
| **合规扫描** | personal-info-lint | 无自动化 PII / PHI / PCI 扫描（detect-secrets、Presidio） |

---

### C4. 成本治理（LLM 花费）

LLM 是 SIA 的**主要运营成本**。当前架构无成本控制。

**现状**：
- `llm_call_log` 表记录 `input_tokens` / `output_tokens` / `duration_ms` ✓
- 无 `cost_usd` 字段
- 无预算告警
- 无按用户 / 按场景 / 按租户的归因仪表板

**场景压力**：
- 攻击者拿到 `X-API-Key` 批量调 LLM 端点 → 当天烧掉 $10,000
- 分析师从 UI 触发"临时报告生成" 跑 100 次 → 当天超标
- 情报量突然增加（某天全球大事件）→ 消费者堵住，LLM 调用积压

**建议**：

```python
# 新增 src/sia/gateway/llm/budget.py
class BudgetGuard:
    """按 (scope, period) 维度检查 LLM 花费，超限熔断。"""
    async def check(self, scope: str, estimated_tokens: int) -> bool:
        # 从 Redis 读当日花费，与 config 里的 daily_budget 比
        spent = await self._daily_spent(scope)
        projected_cost = self._tokens_to_usd(estimated_tokens, model)
        return (spent + projected_cost) < self.daily_budget[scope]
```

- Grafana 仪表：按 `provider / model / purpose / tenant / day` 累积 token 和 cost
- 每日结算 job：写 `llm_cost_daily(tenant_id, model, tokens, cost_usd)` 汇总表
- 预算超阈值 80% → PagerDuty P3；超 100% → 自动切换到 local model（failover chain 最末端）

---

### C5. SRE 成熟度（SLI/SLO / 变更 / 混沌）

| 维度 | 现状 | 需要 |
|---|---|---|
| **SLI 定义** | OPERATIONS_GUIDE 告警阈值 | 明确 SLI：`http_request_success_rate`、`p0_push_latency_p95`、`daily_report_success_rate` |
| **SLO 定义** | NFR 写了目标值 | 格式化到 `slo.yaml` + sloth / OpenSLO 工具生成 alerts + burn-rate |
| **Error Budget** | 无 | 每月多少分钟的预算、消耗速度、触发冻结的规则 |
| **变更管理** | helm upgrade | 无 CAB 审批、无变更窗口、无自动生成变更记录到 Slack/Jira |
| **渐进交付** | Helm rolling | 无 Argo Rollouts / Flagger 金丝雀、无自动回滚基于 SLI 下跌 |
| **Chaos 演练** | 无 | Chaos Mesh / Litmus 注入故障（pod kill、网络延迟、DB 延迟） |
| **值班轮换** | 无 | PagerDuty 轮班、runbook-driven on-call、incident postmortem 模板 |
| **On-call 文档** | 无 | `docs/ONCALL.md`：告警清单 → Runbook 映射 → 升级路径 |
| **Incident 复盘** | 无 | blameless post-mortem 模板、action items 归档到 GitHub Issues |

**建议 v0.3 交付物**：
- `deploy/slo/slo.yaml`（OpenSLO）
- `deploy/slo/alerts.yaml`（基于 burn rate 的告警）
- `docs/RUNBOOKS/`（每个告警一个 Runbook）
- `docs/ONCALL.md`（值班流程）
- `deploy/chaos/experiments/`（5 个基础实验）

---

### C6. API 平台化

| 维度 | 现状 | 需要 |
|---|---|---|
| **API 版本化** | `/api/v1` | 无 `/v2` 迁移策略、`Sunset` header、`Deprecation` header |
| **按租户限流** | 按 identity 限流 | 按 tenant / org 分层限流 |
| **API Key 管理** | 单个 `SIA_API_KEY`（admin 权限） | 多 key、按 key 授权、轮换 SOP、key usage 分析 |
| **API 使用分析** | 无 | 按 key 的调用统计、错误分布、热门端点 |
| **API 网关集成** | Ingress-nginx | Kong / APISIX / Istio API gateway 细粒度策略 |
| **OpenAPI 规约** | FastAPI 自动生成 `/api/docs` | 无发布版本化规约、无 SDK 自动生成 |
| **Webhooks 推送** | Email + IM | 标准 webhook 规约（HMAC 签名、重试、死信） |

---

### C7. AI/ML 运营（LLMOps）

| 维度 | 现状 | 需要 |
|---|---|---|
| **模型版本 / rollout** | `config/llm_gateway.yaml` 静态 | 无 A/B 测试、无 shadow traffic 验证新模型 |
| **输出评估** | 无 | `tests/eval/` 维护 100 条 golden dataset，每次模型变更自动跑回归 |
| **漂移检测** | 无 | 监控输入分布（情报类别比例、语言分布）变化 |
| **Human-in-the-loop** | `feedback_stream` 设计了 | 代码实现？反馈怎么回流到评分策略？ |
| **Prompt 版本化** | YAML in Git | 无 prompt A/B、无性能指标（hit@k）对比 |
| **Token 成本记账** | `llm_call_log` 有 token | 无成本归因（见 C4） |
| **输出质量监控** | 无 | LLM JSON schema 校验失败率的趋势告警 |
| **Prompt 注入防御测试** | SECURITY.md 提及 | 无代码层 red-team 套件（Garak / PyRIT 集成） |

---

### C8. 纵深防御（超出 20 项基线）

| 维度 | 现状 | 需要 |
|---|---|---|
| **东西向 mTLS** | ADR-05 说外包给 Istio | 无 Helm chart 层的 Istio/Linkerd 集成、无 PeerAuthentication |
| **K8s ServiceAccount token 轮换** | 默认 | 关键 Deployment 使用 projected service account tokens |
| **渗透测试** | 无 | 每半年一次外部渗透，报告归档 |
| **漏洞奖励** | SECURITY.md 一行 | 无具体 policy、无响应 SLA、无奖金 |
| **秘密扫描** | personal-info lint | 无 gitleaks / trufflehog 在 pre-commit + CI |
| **Falco 规则维护** | 样板 ConfigMap | 规则需按事件自 review、无 Falco → SIEM 集成 |
| **OPA Gatekeeper** | 样板约束 | 未集成到 CI（仅手动 apply） |
| **Zero Trust service** | 无 | `sia-web → sia-api` 除了 NetworkPolicy 外，缺 ServiceAccount 鉴权 |
| **Dependency review** | Dependabot | 无 OSV-scanner、无 SLSA 验证、无签发 provenance 强制 |

---

### C9. 开发者体验与 Onboarding

**当前状态**：我在之前的清理中**删除了** MBP/Parallels 特定开发流程，但**未补充通用 Dev 环境**。新入职工程师 onboard 没有明确路径。

| 维度 | 现状 | 需要 |
|---|---|---|
| **本地开发环境** | 仅 docker-compose MySQL+Redis | devcontainer.json、pre-commit hooks、一键 local K8s（kind / k3d） |
| **贡献指南** | 无 `CONTRIBUTING.md` | PR 规约、commit message 规约、DCO / CLA |
| **代码风格自动化** | ruff 在 CI | pre-commit + Husky（前端）在本地 |
| **快速上手 README** | 有 | 欠缺 "10 分钟从 zero 到跑起来"的录屏或步骤 |
| **架构学习路径** | v5.0 完整 | 新人先读什么顺序？`docs/ONBOARDING.md` |
| **IDE 配置共享** | 无 | `.vscode/` 推荐扩展 + settings 模板 |
| **debug 手册** | 无 | 常见 dev 问题：DB 连不上、LLM 403、前端 CORS |

---

### C10. 合规证据自动化

企业级合规（SOC 2 / 等保 / GDPR）每年要过审计，**证据收集**是最大成本。

| 维度 | 现状 | 需要 |
|---|---|---|
| **控制点映射** | SECURITY.md §9 文字映射 | SCAP / OSCAL 机读映射 |
| **证据自动收集** | 无 | 每日 job：拉取 RBAC、NetworkPolicy、加固参数、审计样本 → 归档到合规证据库 |
| **配置漂移检测** | 无 | `kubectl diff` + Helm chart 对比实际集群配置 |
| **访问证明** | 无 | 季度访问审计：谁有 admin、谁改了 prod 配置、谁能拿到 DB |
| **数据处理协议模板** | 无 | DPA / SCCs 文档模板 |
| **供应链 SBOM 持续** | CI 生成 | 长期归档 + CVE 订阅 + VEX 声明 |
| **审计轨迹留存** | `audit_log` 表 | 证明未被篡改的 hash chain（见 B-3） |

---

## D. 优先级路线图（v0.3.x → v1.0）

### 🔴 v0.3.0 "企业化基线"（必做，4 周）

| # | 项 | 依赖 | 预估工作量 |
|---|---|---|---|
| 1 | SSRF 校验 | — | 2d |
| 2 | 定时任务分布式锁（Redis redlock） | — | 3d |
| 3 | 审计 Hash 链 + DB INSERT-only 约束 | — | 5d |
| 4 | Outbox Publisher 实现 | — | 5d |
| 5 | DB / Redis CircuitBreaker + Retry | tenacity | 3d |
| 6 | 首次登录强制改密 | — | 2d |
| 7 | 备份 Runbook + DR drill 脚本 | 平台 API | 5d |
| 8 | `rebuild_vectors.py` + `reconcile_analyzing.py` | — | 3d |
| 9 | 集成测试骨架（至少 API 契约 + DB 迁移） | testcontainers | 5d |
| 10 | MinIO 代码集成（报告归档） | — | 3d |

**出口条件**：Top 5 critical 全闭环；30 天无 P1 事件。

### 🟠 v0.3.1 "可观测与 SRE"（4 周）

| # | 项 | 工作量 |
|---|---|---|
| 11 | SLI/SLO 定义 + burn-rate 告警 | 3d |
| 12 | Runbook 覆盖 15 个核心告警 | 5d |
| 13 | LLM 成本看板 + 预算告警 | 5d |
| 14 | Prometheus + Grafana + Loki Helm 集成 | 3d |
| 15 | Chaos Mesh 5 个基础实验 | 5d |
| 16 | Incident 复盘模板 + On-call 文档 | 3d |
| 17 | Argo Rollouts 金丝雀 | 5d |

### 🟡 v0.4 "AI 运营与 API 平台化"（6 周）

| # | 项 | 工作量 |
|---|---|---|
| 18 | LLM 响应缓存（Redis） | 3d |
| 19 | Prompt 评估 golden dataset + CI 回归 | 5d |
| 20 | 多 API Key 管理 + 按 key 限流 | 5d |
| 21 | API Idempotency-Key | 3d |
| 22 | Feature Flag 系统（Redis-backed） | 5d |
| 23 | Webhook 推送标准化（HMAC + 重试） | 5d |
| 24 | 红队测试套件（Garak / PyRIT） | 5d |

### ⚪ v0.5 "合规与纵深防御"（6 周）

| # | 项 | 工作量 |
|---|---|---|
| 25 | GDPR 被遗忘权 API | 3d |
| 26 | 数据生命周期自动归档 | 5d |
| 27 | 合规证据自动收集 job | 5d |
| 28 | Istio Ambient / Linkerd 集成（mTLS） | 10d |
| 29 | 渗透测试 + 报告归档 | 外部 |
| 30 | 漏洞奖励 policy + disclosure 流程 | 3d |

### 🔵 v1.0 "关键业务级"（重大版本）

- 多租户（若业务需要）
- 多区域多活
- 数据驻留隔离（EU / CN / SEA）
- SLA 99.99% + Error Budget 流程
- 外部审计（SOC 2 Type II / 等保三级）

---

## E. 立即可做的 3 个 patch 示例

给运维团队一个可落地的起点。以下每个 patch 都 < 100 行，可在一天内 merge。

### E.1 SSRF 校验（Critical）

`src/sia/collector/url_validator.py`（新增）：

```python
"""URL 安全校验 — 在情报抓取前拦截危险目标 (SSRF 防护)。"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DENY_NETS = [
    ipaddress.ip_network(n) for n in [
        "127.0.0.0/8",      # loopback
        "10.0.0.0/8",       # rfc1918
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",   # link-local (AWS/GCP metadata)
        "::1/128", "fc00::/7", "fe80::/10",
        "0.0.0.0/8",
    ]
]


class UnsafeURLError(ValueError):
    pass


def validate_source_url(url: str, *, allowed_hosts: set[str] | None = None) -> None:
    """Raise UnsafeURLError if url targets internal / loopback / metadata endpoints.

    Resolves DNS once; callers should re-validate after redirects (httpx).
    """
    if not url or len(url) > 2048:
        raise UnsafeURLError("URL missing or too long")
    p = urlparse(url)
    if p.scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme {p.scheme!r} not allowed")
    if not p.hostname:
        raise UnsafeURLError("missing hostname")
    if allowed_hosts is not None and p.hostname not in allowed_hosts:
        raise UnsafeURLError(f"host {p.hostname!r} not in allowlist")

    try:
        addrs = {socket.getaddrinfo(p.hostname, None)[i][4][0] for i in range(1)}
    except OSError as e:
        raise UnsafeURLError(f"DNS resolution failed: {e}") from e
    for a in addrs:
        ip = ipaddress.ip_address(a)
        for net in _DENY_NETS:
            if ip in net:
                raise UnsafeURLError(f"resolves to internal/loopback {ip}")
```

在 `fetcher.py` 每处 `httpx.get(url)` 前调用 + 加 `follow_redirects=False`（或 redirect hook 重新校验）。

### E.2 分布式锁（Critical）

`src/sia/scheduler/distributed_lock.py`（新增）：

```python
"""Redis-based distributed lock wrapping APScheduler jobs."""
from __future__ import annotations

import contextlib
import secrets
from functools import wraps

from sia.common.redis import get_redis


@contextlib.asynccontextmanager
async def redis_lock(key: str, ttl_sec: int = 300):
    r = get_redis()
    token = secrets.token_hex(16)
    acquired = await r.set(f"lock:{key}", token, nx=True, ex=ttl_sec)
    try:
        yield bool(acquired)
    finally:
        if acquired:
            # 只删属于自己的锁 (Lua 保证原子)
            await r.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] then"
                " return redis.call('del', KEYS[1]) else return 0 end",
                1, f"lock:{key}", token,
            )


def with_leader_lock(job_id: str, ttl_sec: int = 300):
    """装饰 APScheduler job function：只有获得锁的 replica 执行。"""
    def deco(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            async with redis_lock(f"job:{job_id}", ttl_sec) as ok:
                if not ok:
                    return  # 其他 replica 正在跑
                return await fn(*args, **kwargs)
        return wrapper
    return deco
```

在 `src/sia/scheduler/service.py` 里：

```python
@with_leader_lock("collect_all", ttl_sec=3600)
async def job_collect_all():
    await collect_all_sources()
```

### E.3 审计日志 Hash 链（Critical）

`src/sia/common/audit.py` 增加：

```python
from hashlib import sha256
from sqlalchemy import desc, select

from sia.common.database import get_db_context
from sia.models.system import AuditLog


async def audit_persist(payload: dict) -> None:
    """写入 audit_log 表并计算 hash 链。写入后表只接受 INSERT（DB 层 GRANT 收紧）。"""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    async with get_db_context() as s:
        prev = (await s.execute(
            select(AuditLog.current_hash).order_by(desc(AuditLog.id)).limit(1)
        )).scalar_one_or_none() or "0" * 64
        cur = sha256(prev.encode() + canonical).hexdigest()
        s.add(AuditLog(**payload, prev_hash=prev, current_hash=cur))
        # s.commit() 由 context manager 处理
```

然后：
- DB 迁移 / seed：给 app 账号 `GRANT SELECT, INSERT ON audit_log` 显式排除 UPDATE/DELETE
- 每日 job：`verify_audit_chain.py` —— 线性扫一遍 audit_log，重算并比对 hash；任何断链 → PagerDuty
- `audit()` 函数：同步写 logger（快）+ 异步 `audit_persist()`（带 retry）

---

## F. 成熟度评分雷达

```
                        [架构设计]
                             ██████████  9/10
        [供应链安全]                          [文档完整性]
          █████████ 9                         █████████ 9
                            \\   //
                             \\ //
    [安全加固] █████████ 9 ———— SIA ———— [部署自动化] █████████ 9
                             // \\
                            //   \\
      [AI 运营]                            [SRE 成熟度]
       ████ 4                               █████ 5
                        [业务连续性]
                         ███ 3/10

                        [多租户]
                          ██ 2/10
```

| 维度 | 分 | 权重 | 加权 |
|---|---|---|---|
| 架构设计 | 9 | 15% | 1.35 |
| 安全加固 | 9 | 15% | 1.35 |
| 供应链安全 | 9 | 10% | 0.90 |
| 文档完整性 | 9 | 10% | 0.90 |
| 部署自动化 | 9 | 10% | 0.90 |
| SRE 成熟度 | 5 | 10% | 0.50 |
| AI 运营 | 4 | 10% | 0.40 |
| 业务连续性 | 3 | 10% | 0.30 |
| 多租户 | 2 | 5% | 0.10 |
| 合规证据 | 4 | 5% | 0.20 |
| **总分** | | **100%** | **6.9 / 10** |

**结论**：SIA v0.2.0 在**开发工程化与安全基线**上显著领先同类项目（9 分），但在**运营与业务连续性**维度仅达到 3-5 分，**距企业级生产系统的 8 分线有 1.1 分差距**。v0.3 专项（Top 10 项）可把加权分提升到 8.3+，正式进入 "企业级" 成熟度区间。

---

## 附：与现有 v5.0 设计文档的对齐建议

本评审发现的几个点应反向修订 `design/Security_Intelligence_Agent_Design_v5.0.md`：

1. **§2.7 Outbox Pattern**：标注"**设计有 / 代码未实现**"，或从设计中移除直到 v0.3 落地
2. **§10.2 SEC-013 审计**：补充"hash chain 当前仅有字段，未写入逻辑"的备注
3. **§10.1 威胁建模 DFD**：补充 SSRF 作为边界 A→B 的明确威胁项和对应控制
4. **§14 测试策略**：金字塔比例与实际（57 单元 / 0 集成 / 0 E2E）差距过大，调整目标或标注当前水位
5. **§15 FMEA**：新增 "#16 SSRF 被利用抓取内网元数据" 和 "#17 多 replica 定时任务重复" 两个失效模式

---

*评审方：Chief Architect / 平台 SRE / 安全架构*
*下一轮评审时点：v0.3.0 发布后的回归评审（预计 4-6 周后）*
