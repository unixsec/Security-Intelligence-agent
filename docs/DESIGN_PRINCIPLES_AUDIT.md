# 设计原则与安全最佳实践 — 自审记录

> 版本：对齐 SIA v0.3（适配层 + 7 路推送 + 30+ 情报源 + 分层简报）
> 目的：逐项核对项目是否遵循了公认的设计原则和安全最佳实践，不合规的在同一 PR 批次内调整。
> 方法：设计原则（SOLID / 12-Factor / Cloud Native / DDD）+ 安全（零信任 / OWASP ASVS / CIS）双框架对照。

---

## 1. SOLID 原则逐项核对

| 原则 | 现状 | 证据 | 本轮整改 |
|---|---|---|---|
| **S** — 单一职责 | ✅ 符合 | adapters/push/* 每个文件一个渠道；collector/* 一源一文件；reporter.exec_brief 专注聚合，exec_render 专注渲染 | 无 |
| **O** — 开闭 | ✅ 符合 | `Registry.register("kind")` 装饰器让新增情报源 / 推送渠道 = 加一个文件，零修改核心 | 无 |
| **L** — Liskov | ✅ 符合 | 所有 `CollectorAdapter._do()` 返回 `list[RawIntelItem]`；所有 `PushAdapter._do()` 返回 `PushResult`；基类契约严格 | 无 |
| **I** — 接口隔离 | ✅ 符合 | `BaseAdapter` 只要求 `_do()`；特定子类按需加 `aopen/aclose`；没有强迫实现无关方法 | 无 |
| **D** — 依赖倒置 | ⚠️ 部分 | 业务层 (reporter/pusher/dispatcher) 依赖抽象 `PushAdapter`，但 `save_and_distribute` 仍有 `from sia.common.minio_client import ...` 的硬依赖 | 保留（MinIO 是接口，已通过 `safe_put_report` 间接解耦）；注记 v0.4 考虑注入 storage adapter |

## 2. 12-Factor App

| # | 因素 | 是否符合 |
|---|---|---|
| I | 代码库 | ✅ 单仓库，main 分支为权威 |
| II | 依赖显式 | ✅ `pyproject.toml` 锁定 |
| III | 配置外置 | ✅ `deployment.config.yaml` + `/etc/sia/secrets/` |
| IV | 后端服务统一 | ✅ MySQL/Redis/Milvus/MinIO 都走 URL 解析 |
| V | 构建/发布/运行分离 | ✅ CI 构建 + Helm 发布 |
| VI | 无状态进程 | ✅ Pod 为 `readOnlyRootFS`，状态全在外部存储 |
| VII | 端口绑定 | ✅ 8080 |
| VIII | 并发通过进程 | ✅ HPA + uvicorn workers + consumer replicas |
| IX | 易处置 | ✅ SIGTERM 优雅退出（SEC-018 + consumer.pipeline） |
| X | 环境一致 | ✅ testcontainers 集成测试 + Docker 统一镜像 |
| XI | 日志流 | ✅ JSON stdout，Loki 聚合 |
| XII | 管理任务 | ✅ alembic migration / seed / verify_audit_chain / reconcile 都是一次性 Job |

## 3. Cloud Native（CNCF 六大）

| 维度 | 现状 |
|---|---|
| 容器化 | ✅ 三 Deployment，多架构镜像 |
| 动态管理 | ✅ K8s + HPA + topologySpread |
| 微服务化 | ✅ api / consumer / web 三进程 + CronJob |
| 服务网格就绪 | ⚠️ 设计中保留挂点；Ambient Istio 是 v0.5 任务 |
| 声明式 API | ✅ Helm + values-prod.yaml |
| 可观测性 | ⚠️ 指标 + 日志 OK，SLI/SLO 定义还是 v0.3.1 工作 |

## 4. 领域驱动设计（DDD）映射

- **Collector 限界上下文**：采集协议适配 → `sia.adapters.collector`
- **Analyzer 限界上下文**：workflow + score + dedup → `sia.analyzer`
- **Reporter 限界上下文**：聚合 + 渲染 + 推送 → `sia.reporter` + `sia.adapters.push`
- **Identity 限界上下文**：auth/rbac → `sia.auth`
- **Gateway (ACL)**：LLM 调用 → `sia.adapters.llm` / `sia.gateway.llm`

✅ 上下文边界清晰，限界上下文之间通过 **事件（Redis Streams + Outbox）** 通讯，而非共享数据库，遵循 DDD 最佳实践。

## 5. OWASP ASVS v4 (Level 2) 关键控制核对

| 分类 | 控制点 | 现状 |
|---|---|---|
| V1 架构 | 1.1 安全需求驱动设计 | ✅ `docs/SECURITY.md` §1 威胁模型 STRIDE |
| V2 鉴权 | 2.1 认证链 | ✅ JWT RS256 + API-Key + LDAP + OIDC |
| V2.2 多因子 | ⚠️ 未强制 | 依赖 IdP（OIDC MFA） — v0.4 加本地 TOTP |
| V3 会话 | 3.2 Token 失效 | ✅ refresh_token 可撤销；改密全撤 |
| V4 访问控制 | 4.1 RBAC | ✅ viewer/analyst/admin 三层 + `require_role()` |
| V5 输入校验 | 5.1 SSRF | ✅ `url_validator.py`（本次新增） |
| V5.2 输入注入 | ✅ pydantic + SQLAlchemy 参数绑定 |
| V5.3 序列化 | ✅ 不 pickle 外部数据；LLM 响应有 JSON schema |
| V7 错误处理 | 7.1 不泄露堆栈 | ✅ prod CORS 限制、无 debug、redaction |
| V8 数据保护 | 8.1 静态加密 | ⚠️ DB 依赖平台；MinIO 建议启用 SSE（v0.4） |
| V8.2 传输加密 | ✅ Ingress TLS + DB/Redis TLS |
| V9 通信 | 9.1 TLS 配置 | ✅ `tls.mode: required`；`rediss://` |
| V10 恶意代码 | 10.1 依赖扫描 | ✅ Dependabot + Trivy + pip-audit |
| V11 业务逻辑 | 11.1 速率限制 | ✅ per-identity + login 独立桶 |
| V12 文件操作 | 12.1 上传校验 | N/A（无用户上传） |
| V13 API | 13.1 输入 schema | ✅ FastAPI + pydantic |
| V14 配置 | 14.2 默认安全 | ✅ 生产强校验，弱默认启动拒绝 |

## 6. 零信任（NIST SP 800-207）对齐

| 核心原则 | 实现 |
|---|---|
| 每次请求鉴权 | ✅ 每请求通过 `get_current_user` 依赖链 |
| 最小权限 | ✅ RBAC + 数据库账号最小授权 |
| 加密 everywhere | ✅ TLS in-transit，Secret at-rest via K8s |
| 可观测 + 动态策略 | ✅ 审计日志链（hash chain）+ 每请求 trace |
| 假设入侵 | ✅ `readOnlyRootFS` + drop ALL caps + seccomp |

## 7. 本轮新增代码原则合规检查

| 文件 | 原则检查 | 结论 |
|---|---|---|
| `adapters/base.py::Registry` | 开闭 + 注册器模式 | ✅ |
| `adapters/collector/base.py::_safe_get` | SSRF + size cap + CT whitelist | ✅ |
| `adapters/push/dispatcher.py::dispatch` | 按订阅路由 + TLP 拦截 + 异步并发 | ✅ |
| `reporter/exec_brief.py::build_brief` | 无副作用，只读数据库聚合 | ✅ |
| `reporter/templates/exec_brief.html.j2` | 选择性 autoescape | ✅ |
| `adapters/push/*.py` 7 渠道 | 每渠道独立 + `resolve_secret` + URL 校验 | ✅ |

## 8. 本次整改列表（已在同一 PR 修复）

| 问题 | 位置 | 修复动作 |
|---|---|---|
| Jinja2 无 autoescape | `exec_render.py` | 使用 `select_autoescape` |
| 推送 webhook 可能指向内网 | `adapters/push/*` | 全部走 `url_validator.validate_source_url` |
| Telegram MarkdownV2 注入 | `adapters/push/telegram.py` | `_escape_mdv2()` 转义保留字符 |
| 飞书 / 钉钉 webhook 签名不足 | `feishu.py`/`dingtalk.py` | HMAC-SHA256 签名计算 |
| 推送 TLP 越权 | `dispatcher.py::_should_deliver` | `_TLP_ORDER` 比较，严格 ≤ |
| 推送失败单点拖累 | `dispatcher.py` | `asyncio.gather` + 单通道异常隔离 |
| 简报 LLM 不可用时整报告失败 | `exec_brief.py::_render_spotlight` | 确定性回退模板 |

## 9. 仍待进入 v0.4 的合规空项

- V2.2 本地 MFA（TOTP 容器）
- V8.1 MinIO SSE-KMS
- K8s ServiceAccount token rotation（projected volumes）
- OPA Gatekeeper 约束完全启用（目前 dryrun）
- SBOM 长期归档 + VEX 声明

---

*自审方：Chief Architect · 审核日期：2026-04-24*
