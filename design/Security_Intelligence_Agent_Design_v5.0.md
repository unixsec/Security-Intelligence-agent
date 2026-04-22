# 安全洞察与情报分析智能体 — 系统设计方案（v5.0）

> **文档版本：** v5.0（企业 K8s 落地版 — 对齐代码 0.2.0）
> **日期：** 2026-04-22
> **作者：** alex &lt;unix_sec@163.com&gt;
> **状态：** 最终稿 — 可直接作为实施与审计依据
> **密级：** 内部机密
> **前置版本：** 本文档是 v4.0（Dify-free 独立 Agent 架构）的后继版本，**取代** v4.0 作为最新设计基线。
>
> **变更摘要（v5.0 vs v4.0）**：
> 1. **服务边界对齐代码**：v4.0 的 6 个服务（gateway/collector/analyzer/reporter/scheduler/web）在 0.2.0 代码中归并为 3 个 Deployment（`sia-api` / `sia-consumer` / `sia-web`），scheduler 内嵌 api，collector/analyzer/reporter 归并到 consumer 的工作流执行引擎。
> 2. **部署形态对齐 Helm chart**：单 `sia` namespace（非 v4.0 的三 namespace 分层）；外部 MySQL/Redis/Milvus/MinIO；单一 `deployment.config.yaml` + `configure.sh` + `deploy-k8s.sh` 一键部署。
> 3. **安全模型升级**：Secret-as-file（`/etc/sia/secrets/`）替代 `envFrom`；容器级 `readOnlyRootFilesystem` + `drop: [ALL]` + `seccomp: RuntimeDefault`；nginx-unprivileged 监听 8080；JWT 默认 **RS256**；per-identity 限流 + 登录 5 req/min/IP 独立桶；结构化审计日志；日志脱敏 filter；TLS 到 DB/Redis/MinIO。
> 4. **供应链安全**：CI 集成 Trivy（HIGH+ 阻断）+ Syft SBOM + Cosign keyless 签名 + attestation + Dependabot + pip-audit。
> 5. **新增图集**：C4 三层架构图、四条关键链路的序列图、情报与工作流状态机、ER 图、带信任边界的威胁建模 DFD、K8s 部署拓扑 (0.2.0 版)。
> 6. **新增附录**：架构决策记录 (ADR) ×12、非功能需求 (NFR) 表、失效模式与影响分析 (FMEA) 表。

---

## 目录

- [第 1 部分：战略概述](#第-1-部分战略概述)
  - [1.1 执行摘要](#11-执行摘要)
  - [1.2 项目背景与目标](#12-项目背景与目标)
  - [1.3 用户画像与场景](#13-用户画像与场景)
  - [1.4 设计原则](#14-设计原则)
- [第 2 部分：系统架构（C4 模型）](#第-2-部分系统架构c4-模型)
  - [2.1 Level 1 — 系统上下文图](#21-level-1--系统上下文图)
  - [2.2 Level 2 — 容器图](#22-level-2--容器图)
  - [2.3 Level 3 — 关键组件图](#23-level-3--关键组件图)
  - [2.4 核心数据流（业务视角）](#24-核心数据流业务视角)
  - [2.5 服务边界与通信](#25-服务边界与通信)
  - [2.6 消息可靠性与幂等](#26-消息可靠性与幂等)
  - [2.7 跨存储最终一致性](#27-跨存储最终一致性)
- [第 3 部分：序列图（关键流程）](#第-3-部分序列图关键流程)
  - [3.1 用户登录（本地 + OIDC）](#31-用户登录本地--oidc)
  - [3.2 情报采集 → 分析 → 入库](#32-情报采集--分析--入库)
  - [3.3 报告生成与推送](#33-报告生成与推送)
  - [3.4 Secret 轮换](#34-secret-轮换)
- [第 4 部分：状态机](#第-4-部分状态机)
  - [4.1 情报生命周期](#41-情报生命周期)
  - [4.2 工作流执行状态](#42-工作流执行状态)
  - [4.3 用户账号状态](#43-用户账号状态)
- [第 5 部分：技术选型](#第-5-部分技术选型)
- [第 6 部分：LLM 统一网关](#第-6-部分llm-统一网关)
  - [6.1 设计目标](#61-设计目标)
  - [6.2 架构分层](#62-架构分层)
  - [6.3 熔断与失败链](#63-熔断与失败链)
  - [6.4 云端脱敏](#64-云端脱敏)
- [第 7 部分：工作流引擎](#第-7-部分工作流引擎)
- [第 8 部分：数据架构](#第-8-部分数据架构)
  - [8.1 ER 图](#81-er-图)
  - [8.2 关键表结构](#82-关键表结构)
  - [8.3 向量库设计](#83-向量库设计)
  - [8.4 数据生命周期](#84-数据生命周期)
- [第 9 部分：部署架构（0.2.0）](#第-9-部分部署架构020)
  - [9.1 K8s 拓扑](#91-k8s-拓扑)
  - [9.2 网络架构](#92-网络架构)
  - [9.3 集中化配置与一键部署](#93-集中化配置与一键部署)
  - [9.4 滚动更新与金丝雀](#94-滚动更新与金丝雀)
- [第 10 部分：安全模型](#第-10-部分安全模型)
  - [10.1 威胁建模（带信任边界的 DFD）](#101-威胁建模带信任边界的-dfd)
  - [10.2 20 项加固基线](#102-20-项加固基线)
  - [10.3 密钥管理](#103-密钥管理)
  - [10.4 审计与合规](#104-审计与合规)
- [第 11 部分：非功能需求（NFR）](#第-11-部分非功能需求nfr)
- [第 12 部分：可观测性](#第-12-部分可观测性)
- [第 13 部分：可运维性](#第-13-部分可运维性)
- [第 14 部分：测试策略](#第-14-部分测试策略)
- [第 15 部分：风险与应急（FMEA）](#第-15-部分风险与应急fmea)
- [第 16 部分：实施规划](#第-16-部分实施规划)
- [附录 A：架构决策记录（ADR）](#附录-a架构决策记录adr)
- [附录 B：NFR 指标详表](#附录-bnfr-指标详表)
- [附录 C：FMEA 详表](#附录-cfmea-详表)
- [附录 D：v5.0 vs v4.0 差异总表](#附录-dv50-vs-v40-差异总表)
- [附录 E：缩略语](#附录-e缩略语)

---

# 第 1 部分：战略概述

## 1.1 执行摘要

**SIA（Security Intelligence Agent）** 是企业内部署的 AI 驱动**安全情报聚合与分析平台**：

- 自动从 **公网（RSS/NVD/CISA）/ 内部源** 拉取安全情报；
- 通过 **多 LLM 网关**（本地 + 云端）做分级、打分、IoC 抽取、影响评估、ATT&CK 映射；
- 以**日报 / 周报 / 紧急预警**推送给安全团队与管理层，并通过 **Web 控制台 + REST API** 支持二次消费。

本版设计确保：
- **企业 K8s 一键部署**（单一配置入口、幂等脚本、自动生成 Secret）；
- **零默认凭据**（应用在生产环境强校验，缺 Secret 即拒绝启动）；
- **容器硬化到 Pod Security Standard Restricted**（readOnlyRootFilesystem + dropAllCaps + seccomp + 非 root + topologySpread）；
- **供应链可审计**（Trivy + SBOM + Cosign 签名 + 依赖自动更新 + 个人信息 lint）；
- **可观测 + 可审计**（结构化 JSON 日志、独立 `sia.audit` logger、Prometheus 指标、OTLP 追踪）。

## 1.2 项目背景与目标

### 1.2.1 企业画像

- 大型已上市跨国企业，主营智能网联汽车制造与销售；
- 市场覆盖：欧盟、中国大陆、东南亚；
- 安全关注优先级：企业通用 IT 安全（办公网络、ERP/PLM/CRM/MES、邮件、AD、云、数据库、终端） > 汽车行业特定（车联网、自动驾驶、OTA、智能座舱、充电）。

### 1.2.2 技术基础设施

- 企业内部已私有化部署 LLM，提供 OpenAI 兼容 API（默认 DeepSeek，可切 Qwen / GLM / Kimi / Gemini / Claude）；
- 所有组件运行于企业私有 K8s 集群；
- 数据层（MySQL / Redis / Milvus / MinIO）由平台团队托管或集群内自运营。

### 1.2.3 目标

| 目标 | 成功度量 |
|---|---|
| 每日抓取 ≥ 2000 条情报，过滤去重后入分析队列 | 日均入库 ≥ 300 条有效情报 |
| P0 情报 10 分钟内识别并推送 | P0 告警延迟 P95 ≤ 10 min |
| 每日报告 08:00 自动生成 | 每日报告生成成功率 ≥ 99% |
| API 可用性 | 月度可用性 ≥ 99.5% |
| 安全合规 | 全部 20 项加固基线验收通过（见 §10.2） |

## 1.3 用户画像与场景

| 画像 | 角色 | 关注 | 主要入口 |
|---|---|---|---|
| **CISO / CTO** | 管理层 | 当日高优情报摘要、影响评估 | 每日邮件 + Web 仪表盘 |
| **SOC 值班 / 应急响应** | 一线运维 | P0/P1 实时告警、IoC | 企业 IM 推送 + Web 列表 |
| **安全分析师** | Analyst | 全量情报检索、分类、打分、报告导出 | Web 控制台 |
| **SIEM / SOAR 集成方** | 机器账户 | 通过 REST API 拉取结构化数据 | `X-API-Key` 调 `/api/v1/intelligence` |

## 1.4 设计原则

1. **一个服务单一职责，但别为了微服务而微服务** —— 最终合并为 3 个 Deployment。
2. **默认拒绝（Default Deny）** —— 鉴权、CORS、NetworkPolicy、容器能力。
3. **Secret 永不落盘到仓库，永不注入环境变量** —— 文件挂载 + 只读 + 0400。
4. **幂等优先** —— 配置、部署、消费者 ACK 均幂等。
5. **可观测是 Day 1 特性** —— 结构化日志、metrics、trace 从第一次上线即存在。
6. **审计独立于业务日志** —— 敏感操作写入独立 logger，便于 SIEM 单独摄取。
7. **容器被视为可完全丢失的单位** —— 无本地状态，所有数据写外部存储。
8. **测试与部署同等公民** —— CI 包含安全扫描；部署脚本含冒烟测试；删除任何安全控制要通过 lint。

---

# 第 2 部分：系统架构（C4 模型）

本章用 C4 模型（Context / Container / Component）分层呈现，先宏观后微观，覆盖 v4.0 未明确的"角色外部视角"和"容器级部署形态"。

## 2.1 Level 1 — 系统上下文图

```
                          ┌───────────────────────────────────────┐
                          │      企业 K8s 集群  /  SIA 系统        │
                          │                                       │
    ┌─────────────┐       │  ╔════════════════════════════════╗   │
    │ 安全分析师  │──────▶│  ║                                ║   │
    │ SOC 值班    │       │  ║    SIA (Security Intelligence  ║   │
    │ CISO/CTO    │◀──────│  ║          Agent)                ║   │
    └─────────────┘  Web  │  ║                                ║   │
                          │  ║  - 情报聚合  - LLM 分析        ║   │
    ┌─────────────┐       │  ║  - 去重评分  - 报告生成        ║   │
    │ SIEM/SOAR   │──REST─│─▶║  - 审计日志  - RBAC            ║   │
    │ (机器账户)  │◀──────│  ║                                ║   │
    └─────────────┘       │  ╚═══════╦══════════════╦═════════╝   │
                          │          │              │             │
                          └──────────┼──────────────┼─────────────┘
                                     │              │
                              外部情报源     企业基础设施
                          ┌───────┴───────┐   ┌─────┴─────────┐
                          │ NVD / CISA    │   │ 企业 LLM      │
                          │ RSS / 网站    │   │ (DeepSeek/    │
                          │ 公众号 / API  │   │  Qwen/GLM)    │
                          └───────────────┘   │ 云 LLM (Gemini│
                                              │  Claude/GPT)  │
                                              │ MySQL/Redis/  │
                                              │ Milvus/MinIO  │
                                              │ 企业出口代理  │
                                              │ SMTP/IM       │
                                              └───────────────┘
```

**边界**：SIA 是情报层，不做 EDR/XDR、漏扫、SOAR 编排；下游处置由企业现有 SOC 工具链消费 SIA 的 API / 推送。

## 2.2 Level 2 — 容器图

将 "SIA 系统" 展开为实际 K8s Deployment / 外部依赖：

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                         K8s Namespace: sia                                │
 │                                                                           │
 │   ┌──────────────────────┐          ┌─────────────────────────┐           │
 │   │  Ingress (nginx)     │──TLS────▶│  Service  sia-web :80   │           │
 │   │  host: <INGRESS_HOST>│          │  → sia-web Pods (UID101)│           │
 │   └──────────┬───────────┘          │  nginx-unprivileged:8080│           │
 │              │                      └────────────┬────────────┘           │
 │              │                                   │ proxy /api/*           │
 │              │                                   ▼                        │
 │              │                      ┌─────────────────────────┐           │
 │              └─────────────────────▶│  Service  sia-api :8080 │           │
 │                                     │  → sia-api Pods (UID1000│           │
 │                                     │  FastAPI + Uvicorn      │           │
 │                                     │  + Scheduler (APSched.) │           │
 │                                     │  + LLM Gateway + Auth   │           │
 │                                     │  HPA 2→8 @ CPU 70%      │           │
 │                                     └───────┬─────────────────┘           │
 │                                             │                             │
 │                                             │  XADD/XREAD                 │
 │                                             ▼                             │
 │                                     ┌─────────────────────────┐           │
 │                                     │  sia-consumer Pods      │           │
 │                                     │  (UID 1000)             │           │
 │                                     │  Redis Streams 消费者组 │           │
 │                                     │  + Workflow Engine      │           │
 │                                     │  + Collector tasks      │           │
 │                                     │  + Analyzer tasks       │           │
 │                                     │  + Reporter tasks       │           │
 │                                     │  terminationGracePeriod:│           │
 │                                     │    90s (SIGTERM drain)  │           │
 │                                     └──────────┬──────────────┘           │
 │                                                │                          │
 │   ┌───────────────────────────────────────────┼───────────────────────┐   │
 │   │ 都通过 Secret 文件挂载 /etc/sia/secrets/  │                       │   │
 │   │ 都 readOnlyRootFilesystem + drop:[ALL]    │                       │   │
 │   │ + seccomp:RuntimeDefault                  │                       │   │
 │   │ emptyDir: /tmp /home/sia/.cache /var/run  │                       │   │
 │   │ ConfigMap: sia-config   Secret: sia-secrets                       │   │
 │   │ NetworkPolicy: sia-network-policy（见 §9.2）                       │   │
 │   └─────────────────────────────────────────────────────────────────────┘│
 └─────────────────────┬─────────────────┬─────────────────┬─────────────────┘
                       │                 │                 │
                       ▼                 ▼                 ▼
           ┌────────────────┐ ┌──────────────────┐ ┌─────────────────┐
           │  MySQL 8.0     │ │  Redis 7         │ │  Milvus 2.4     │
           │  TLS required  │ │  TLS rediss://   │ │  + MinIO (S3)   │
           │  async pool 10 │ │  Streams + Cache │ │  向量 / 报告     │
           │  (外部托管)    │ │  (外部托管)      │ │  (外部托管)     │
           └────────────────┘ └──────────────────┘ └─────────────────┘

           ┌────────────────┐ ┌──────────────────┐ ┌─────────────────┐
           │  企业出口代理  │ │  企业 LLM        │ │  SMTP / IM      │
           │  Squid/Nginx   │ │  (vLLM/Ollama    │ │  Webhook         │
           │  审计+白名单   │ │   OpenAI 兼容)   │ │                  │
           └────────┬───────┘ └──────────────────┘ └─────────────────┘
                    │
                    ▼
              云端 LLM API
              (Claude/Gemini/ChatGPT)
```

**v4.0 → v5.0 关键变化**：
- 六服务 → 三 Deployment（api 合并 gateway+scheduler，consumer 合并 collector/analyzer/reporter，web 独立）
- 单 namespace `sia`（外部数据层不归 SIA Helm chart 管）
- 所有内部容器身份均为 UID 1000（`sia`），唯 web 为 UID 101（nginx-unprivileged）

## 2.3 Level 3 — 关键组件图

### 2.3.1 `sia-api` 容器内部组件

```
┌──────────────────────────────────────────────────────────────────────┐
│                     sia-api (Python process)                          │
│                                                                       │
│  Uvicorn (uvloop + httptools, workers=4)                              │
│    │                                                                  │
│    ▼                                                                  │
│  FastAPI app (sia.main:create_app)                                    │
│   ├─ Middleware (顺序从外到内):                                       │
│   │    1. RateLimitMiddleware (per-identity + login-specific)        │
│   │    2. CORSMiddleware (prod: allow_origins=[])                    │
│   ├─ Routers /api/v1/:                                                │
│   │    auth / users / intelligence / sources / reports / dashboard   │
│   ├─ Dependencies:                                                    │
│   │    get_current_user (Bearer JWT → API-Key → dev-anon)            │
│   │    require_role(min_role)                                         │
│   │    get_db (AsyncSession, commit on success/rollback on exc)      │
│   ├─ Lifespan:                                                        │
│   │    install_redaction (logging filter)                            │
│   │    ensure_consumer_groups (Redis)                                │
│   │    scheduler.start (APScheduler — 触发报告/巡检)                  │
│   └─ Routers 内部会调用:                                              │
│        LLMGateway (对话 / 嵌入 / 结构化输出)                          │
│        audit()   (敏感操作写 sia.audit logger)                        │
│                                                                       │
│  读 /etc/sia/secrets/SIA_* 作为 Secret 来源                           │
│  通过 ConfigMap 读 SIA_MYSQL_HOST 等非敏感配置                        │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3.2 `sia-consumer` 容器内部组件

```
┌──────────────────────────────────────────────────────────────────────┐
│                   sia-consumer (Python process)                       │
│                                                                       │
│  asyncio event loop                                                   │
│    │                                                                  │
│    ▼                                                                  │
│  run_analysis_consumer()  (sia.analyzer.pipeline)                     │
│    ├─ 信号处理: SIGTERM/SIGINT → stop_event.set()                    │
│    ├─ Workflow Engine:                                                │
│    │    StepRegistry (llm_call / python_func)                        │
│    │    WorkflowEngine.load_all('workflows/*.yaml')                  │
│    ├─ 循环:                                                           │
│    │    messages = await redis.xreadgroup(                            │
│    │       'analyzer-group', 'analyzer-1',                            │
│    │       {'raw_intel_stream': '>'}, count=5, block=5000)           │
│    │    for msg in messages:                                          │
│    │       load_intel_from_db(msg.intel_id)                           │
│    │       ctx = WorkflowContext('analyze_intel')                     │
│    │       ctx.set('input', intel_data)                               │
│    │       await engine.execute('analyze_intel', ctx)                 │
│    │       → LLM call (classify/score/extract-ioc)                    │
│    │       → python_func (persist + priority)                         │
│    │       → 可能 publish_to_stream(emergency_stream)                 │
│    │       xack                                                       │
│    │    if stop_event.set(): break                                    │
│    │                                                                  │
│    同样读 /etc/sia/secrets/ + ConfigMap                               │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3.3 LLM Gateway 组件（`sia.gateway.llm`）

```
┌──────────────────────────────────────────────────────────────────────┐
│                        LLMGateway                                     │
│                                                                       │
│   register_provider("deepseek-r1", LocalOpenAICompatProvider)         │
│   register_provider("gemini-pro",  CloudGoogleProvider)               │
│   register_provider("claude-sonnet", CloudAnthropicProvider)          │
│   register_provider("gpt-4o",       CloudOpenAIProvider)              │
│                                                                       │
│   async def chat_completion(messages, model=default, purpose=None):   │
│      1. 选择 primary = router.pick(model, purpose)                    │
│      2. 若为云端 provider: anonymize(messages)                        │
│      3. breaker = circuit_breaker[primary]                            │
│         if breaker.is_open(): raise / use fallback                    │
│      4. try:                                                          │
│           resp = await provider.chat_completion(...)                  │
│           breaker.record_success()                                    │
│         except ProviderError:                                         │
│           breaker.record_failure()                                    │
│           for alt in failover_chain[purpose or model]:                │
│              try: return await providers[alt](...)                    │
│              except: continue                                         │
│           raise LLMGatewayError                                       │
│      5. 若为云端 provider: 反向替换脱敏占位符 → 还原真实值            │
│      6. llm_call_log.insert(provider, model, tokens, duration, ok)    │
│                                                                       │
│   Provider 实现:                                                       │
│      LocalOpenAICompatProvider  (AsyncOpenAI, base_url=企业内网)      │
│      CloudAnthropicProvider     (anthropic SDK, via 企业出口代理)     │
│      CloudGoogleProvider        (google.generativeai)                 │
│      CloudOpenAIProvider        (openai SDK)                          │
│                                                                       │
│   横切:                                                               │
│      CircuitBreaker  (连续失败阈值 5, 恢复窗口 60s)                   │
│      RateLimiter     (按 provider 分桶，防配额耗尽)                   │
│      RetryPolicy     (指数回退 3 次)                                  │
│      Anonymizer      (正则 + 白名单, 出云前替换 IP/员工名)            │
│      LLMCallLog      (MySQL: provider/model/tokens/duration/ok)       │
└──────────────────────────────────────────────────────────────────────┘
```

## 2.4 核心数据流（业务视角）

```
                        ┌─────────────────────────────────┐
                        │       外部情报源（互联网）        │
                        │  RSS │ NVD/CISA │ 网站 │ 公众号  │
                        └───────────────┬─────────────────┘
                                        │  (经企业出口代理，域名白名单)
                                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│  sia-consumer — Collector 任务 (CronJob 调度自 sia-api Scheduler)    │
│    ① 抓取 → ② 清洗 + 语言检测 → ③ 指纹去重 (Redis SHA1)              │
│    ④ 近似去重 (Milvus KNN < 0.1)                                      │
│    ⑤ 落库 intelligence 表 + 写 raw_intel_stream                       │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  sia-consumer — Analyzer 任务（XREADGROUP raw_intel_stream）         │
│    加载情报 + 资产匹配                                                │
│    执行 workflow 'analyze_intel':                                     │
│      ├─ llm_call: 分类 + 严重度   (LLM Gateway)                      │
│      ├─ llm_call: IoC 抽取        (LLM Gateway)                      │
│      ├─ llm_call: 影响 + ATT&CK  (LLM Gateway)                       │
│      ├─ python_func: 5 维评分 + 优先级                                │
│      └─ python_func: 持久化 (MySQL) + 写 analyzed_stream              │
│    P0/P1 → publish_to_stream('emergency_stream')                      │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
          ┌──────────────────┴───────────────────────┐
          │                                          │
          ▼                                          ▼
┌────────────────────────┐                ┌──────────────────────────┐
│  sia-consumer — Emerg  │                │  sia-consumer — Reporter │
│  紧急推送 (≤ 10 min)   │                │  Daily 08:00 / Weekly    │
│  Email + IM Webhook    │                │  汇总 → LLM 生成摘要 →   │
│                        │                │  Jinja2 → WeasyPrint PDF │
│                        │                │  → MinIO 归档            │
│                        │                │  → push_task_stream      │
└────────────────────────┘                └────────────┬─────────────┘
                                                       │
                                                       ▼
                                          ┌──────────────────────────┐
                                          │  SMTP / IM Webhook       │
                                          │  (经企业出口代理)        │
                                          └──────────────────────────┘

所有阶段中的数据库事务均遵循 Outbox Pattern：业务写 + 消息写在同一事务，
由独立的 outbox_publisher 任务把 outbox 表的条目搬到 Redis Streams，
确保"业务落库"与"消息发出"原子性。
```

## 2.5 服务边界与通信

| 组件 | 入站协议 | 出站协议 | 认证 |
|---|---|---|---|
| `sia-web` | HTTP/80 (Service) ← Ingress | HTTP → sia-api:8080 (Service DNS) | — |
| `sia-api` | HTTP/8080 ← Ingress 及 sia-web | MySQL TLS、Redis TLS、Milvus、MinIO HTTPS、LLM HTTPS（经代理） | Bearer JWT（RS256）/ X-API-Key（header） |
| `sia-consumer` | — (无入站) | 同 sia-api | Service account + 同样的 Secret |

内部 Service-to-Service 通过 K8s Service DNS（`sia-api.sia.svc.cluster.local`）。**不跨 namespace**，所有东向流量在本 NS 内完成；南北向由 Ingress + NetworkPolicy 控制。

## 2.6 消息可靠性与幂等

### 2.6.1 Redis Streams 可靠消费

```
Producer (sia-api 或 sia-consumer 的上游 step):
  XADD raw_intel_stream * intel_id 12345 src 1 trace_id xyz

Consumer (sia-consumer.analyzer-group.analyzer-1):
  loop:
    msgs = XREADGROUP GROUP analyzer-group analyzer-1
             COUNT 5 BLOCK 5000
             STREAMS raw_intel_stream >
    for msg in msgs:
      try:
        process(msg)
        XACK raw_intel_stream analyzer-group msg.id
      except TransientError:
        # 不 ACK，下次 redelivery（> 对应于 pending list 索取）
        pass
      except PoisonMessage:
        # 搬到 DLQ 然后 ACK，防止无限 redelivery
        XADD dead_letter_stream ...
        XACK raw_intel_stream analyzer-group msg.id

Pending messages 超时（未 ACK）:
  XPENDING / XCLAIM — 由另一个维护任务接管失联消费者的未决消息。
```

### 2.6.2 幂等键

| 场景 | 幂等键 | 作用点 |
|---|---|---|
| 情报落库 | `SHA1(url + published_at)` 作 `intelligence.fingerprint` UNIQUE 索引 | 重复抓取不重复入库 |
| LLM 调用账本 | `request_id = UUIDv4` 贯穿一次分析 | 重复消费消息时不重复计账 |
| 报告生成 | `(date, type)` UNIQUE | 同日同类型报告只一份 |
| 推送 | `(intel_id, channel, recipient)` UNIQUE | 同情报对同人只推一次 |
| Secret 轮换 | configure.sh 输出的 Secret 用 `resourceVersion` 做版本；apply 是幂等的 |

## 2.7 跨存储最终一致性

SIA 写多个存储（MySQL + Redis + Milvus + MinIO）时，**以 MySQL 事务为权威**，其他存储通过 Outbox Pattern 异步落盘：

```
Transaction:
   INSERT INTO intelligence (...)          -- 权威
   INSERT INTO outbox (event, payload, status='pending') -- 本地消息表
   COMMIT

Outbox Publisher (后台任务, 每 100ms 扫一次):
   SELECT * FROM outbox WHERE status='pending' LIMIT 100
   for event in events:
      XADD raw_intel_stream ... event.payload
      UPDATE outbox SET status='sent' WHERE id=event.id

Milvus / MinIO 写入 (在 consumer 侧):
   写 Milvus 失败 → 幂等重试（带请求 ID，已写即 skip）
   写 MinIO 失败 → 重试；失败次数超限进 DLQ 人工介入
```

**回补**：Milvus 向量丢失可根据 MySQL 情报全量重建（`rebuild_vectors.py`）；MinIO 报告丢失可根据 MySQL report 元数据从同日数据重新生成。

---

# 第 3 部分：序列图（关键流程）

## 3.1 用户登录（本地 + OIDC）

```
 Actor     Browser         sia-web(nginx)     sia-api          MySQL         sia.audit
   │            │                │               │                │              │
   │── POST ───▶│                │               │                │              │
   │ /login     │── POST ───────▶│               │                │              │
   │ {u,p}      │ /api/v1/login  │── proxy ─────▶│                │              │
   │            │                │               │                │              │
   │            │                │               │─ RateLimiter   │              │
   │            │                │               │  (5 req/min/IP for login)    │
   │            │                │               │                │              │
   │            │                │               │── SELECT user WHERE username= │
   │            │                │               │               ─▶│              │
   │            │                │               │◀─ user row ────│              │
   │            │                │               │                │              │
   │            │                │               │  verify_password(bcrypt)      │
   │            │                │               │                │              │
   │            │                │               │  if fail:                     │
   │            │                │               │    ++failed_login_count       │
   │            │                │               │    UPDATE user SET locked…    │
   │            │                │               │    await db.commit()          │
   │            │                │               │    audit(user.login,failure)──▶
   │            │                │               │    raise HTTPException(401)   │
   │            │                │               │                │              │
   │            │                │               │  if success:                  │
   │            │                │               │    create_access_token (RS256)│
   │            │                │               │    create_refresh_token       │
   │            │                │               │    INSERT refresh_token_hash  │
   │            │                │               │    audit(user.login,success)──▶
   │            │◀─────── 200 {access,refresh} ──│                │              │
   │◀───────────│                │               │                │              │
```

OIDC 变体（`/api/v1/auth/oidc/authorize` + `/callback`）走 IdP 重定向；返回 code 后 sia-api 用 Authlib 交换 id_token，首次登录用户按 `role_mapping` 自动建本地 user 行。

## 3.2 情报采集 → 分析 → 入库

```
 Scheduler (sia-api)     sia-consumer        LLM Gateway     MySQL/Redis/Milvus
     │                        │                  │                 │
     │── trigger WF-COLLECT-RSS                   │                 │
     │   (CronJob 0 */4 * * *)                    │                 │
     │── XADD collect_task_stream ────────────────│                ─▶Redis
     │                        │                  │                 │
     │                        │◀─ XREADGROUP ────────────────────── Redis
     │                        │                  │                 │
     │                        │  Collector step:                    │
     │                        │    httpx.GET rss_url (via 代理)     │
     │                        │    parse feedparser                 │
     │                        │    for entry:                       │
     │                        │      fingerprint=SHA1(url|pubdate)  │
     │                        │      SELECT 1 WHERE fingerprint=… ─▶│MySQL
     │                        │      if exists: skip                │
     │                        │      embed(entry.content) ── ─────▶ LLM (embedding)
     │                        │      ◀──── vector (768)             │
     │                        │      Milvus.kNN(vec, topk=5)  ─────▶Milvus
     │                        │      if max_sim > 0.9: mark dup     │
     │                        │      BEGIN                           │
     │                        │      INSERT intelligence            ─▶MySQL
     │                        │      INSERT outbox(raw_intel, pay)  ─▶MySQL
     │                        │      COMMIT                          │
     │                        │  XACK collect_task_stream            │
     │                        │                                      │
     │                        │   (outbox publisher 搬运)            │
     │                        │── XADD raw_intel_stream ──────────── Redis
     │                        │                                      │
     │                        │◀─ XREADGROUP raw_intel_stream ─────  Redis
     │                        │                                      │
     │                        │  Analyzer (WorkflowEngine):          │
     │                        │    step1: llm_call classify ───────▶ LLM Gateway
     │                        │           ◀──── {cat,severity}       │
     │                        │    step2: llm_call extract-ioc ─────▶ LLM Gateway
     │                        │           ◀──── {iocs:[...]}         │
     │                        │    step3: python_func score+prio     │
     │                        │    step4: python_func persist ─────▶MySQL
     │                        │           UPDATE intelligence SET... │
     │                        │           INSERT intelligence_ioc     │
     │                        │           INSERT outbox(analyzed)     │
     │                        │    if priority in (P0,P1):           │
     │                        │       INSERT outbox(emergency)        │
     │                        │  XACK raw_intel_stream                │
     │                        │── (outbox publisher)                  │
     │                        │── XADD analyzed_stream / emergency ─ Redis
```

## 3.3 报告生成与推送

```
 Scheduler           sia-consumer (Reporter)    LLM            MySQL          MinIO      SMTP/IM
    │                      │                    │              │               │          │
    │── CronJob 0 6 * * 1-5│                    │              │               │          │
    │── XADD report_request_stream {type:daily} ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─▶  │          │
    │                      │                    │              │               │          │
    │                      │◀── XREADGROUP ──── Redis                                     │
    │                      │                                                              │
    │                      │ SELECT intel WHERE created_at between(D-1, D)  ─▶│          │
    │                      │◀──── 120 条 ─────────────────────────────────────│          │
    │                      │                                                              │
    │                      │ llm_call: "summarize for execs" ──▶              │          │
    │                      │ ◀──── 摘要 markdown                 LLM          │          │
    │                      │                                                              │
    │                      │ render Jinja2 template → HTML                                │
    │                      │ WeasyPrint HTML → PDF                                        │
    │                      │ minio.put_object(bucket='sia-reports',                       │
    │                      │                  key='daily/2026-04-22.pdf', ..) ──────────▶│
    │                      │ INSERT report(..) ──────────────────────────────▶│          │
    │                      │ INSERT outbox(push_task, channels=[email,im])               │
    │                      │ (outbox publisher) → XADD push_task_stream ───────          │
    │                      │                                                              │
    │                      │◀── XREADGROUP push_task_stream                               │
    │                      │ for channel in channels:                                     │
    │                      │   Email: aiosmtplib.send (signed, to CISO+SOC)  ──────────▶ │
    │                      │   IM:    httpx.POST webhook (签名校验) ────────────────────▶│
    │                      │ XACK
```

## 3.4 Secret 轮换

```
 Operator            configure.sh         kubectl              K8s API         Pods
    │                    │                   │                     │              │
    │ edit deployment.config.yaml            │                     │              │
    │  （清空要轮换的 secrets 字段）         │                     │              │
    │                    │                   │                     │              │
    │── ./configure.sh --generate-secrets ──▶│                     │              │
    │                    │                                                        │
    │  校验必填占位符                                                              │
    │  对清空字段：openssl rand / RSA keypair                                     │
    │  再次写回 deployment.config.yaml (600)                                      │
    │  渲染 deploy/helm/sia/values-prod.yaml                                      │
    │  渲染 deploy/rendered/sia-secrets.yaml (600)                                │
    │                    │                                                        │
    │── kubectl apply -f deploy/rendered/sia-secrets.yaml ────────────────────────│
    │                    │                   │── PUT Secret ──────▶│              │
    │                    │                   │                     │ ConfigMap   │
    │                    │                   │                     │ /Secret      │
    │                    │                   │                     │ 的 update    │
    │                    │                   │                     │ 不会自动重载 │
    │                    │                   │                     │ 已挂载 pod  │
    │                    │                   │                     │              │
    │── kubectl rollout restart deployment -n sia ────────────────────────────────│
    │                    │                   │── Patch Deploy ────▶│              │
    │                    │                   │                     │              │
    │                    │                   │                     │    rolling  │
    │                    │                   │                     │◀─ 新 pod ──  │
    │                    │                   │                     │              │
    │                    │                   │                     │   新 pod 启  │
    │                    │                   │                     │  动时读      │
    │                    │                   │                     │  /etc/sia/   │
    │                    │                   │                     │  secrets/    │
    │                    │                   │                     │  中新值      │
    │                    │                   │                     │              │
    │                    │                   │                     │  旧 access   │
    │                    │                   │                     │  token 在过  │
    │                    │                   │                     │  期前仍有效  │
    │                    │                   │                     │  (30min)    │
```

**推荐生产路径**：用 external-secrets / sealed-secrets / Vault Agent 从外部 secret manager 同步，这样不依赖 `configure.sh --generate-secrets` 人工执行，轮换可自动。

---

# 第 4 部分：状态机

## 4.1 情报生命周期

```
                         ┌──────────────────┐
                         │   created         │  ← Collector INSERT
                         │ (pending_analysis)│
                         └────────┬──────────┘
                                  │ xadd raw_intel_stream
                                  ▼
                         ┌──────────────────┐
                         │    analyzing      │  ← Consumer starts workflow
                         └──┬──────────────┬─┘
                            │              │
            workflow done   │              │  workflow failed after retry
                            ▼              ▼
                 ┌─────────────────┐   ┌──────────┐
                 │    analyzed      │   │   dlq    │  → 人工介入
                 │ (P0/P1/P2/P3)   │   └──────────┘
                 └────┬────────┬──┘
                      │        │ analyst standrard / feedback
           priority P0│        │
                      ▼        ▼
            ┌──────────────┐ ┌──────────────┐
            │  emergency_   │ │   reviewed    │  ← Analyst 确认/修正
            │   dispatched  │ └──┬────────────┘
            └──────┬───────┘    │
                   │            │  可能被反馈标记
                   ▼            ▼
            ┌──────────────────────────────┐
            │     archived / suppressed    │
            │  (archived = 历史查询; suppressed = 误报不再展示)
            └──────────────────────────────┘
```

## 4.2 工作流执行状态

```
   start                                         reached max retries
     │                                                  ▲
     ▼                                                  │
 ┌───────┐  step 执行异常   ┌──────────┐               │
 │running│ ─────────────▶  │ retrying │ ──重试成功──▶ │
 └───┬───┘                 └──────────┘               │
     │ 全部 step ok                                    │
     ▼                                                  │
 ┌───────┐                                              │
 │  ok   │                                              │
 └───────┘                                              │
     ▲                                                  │
 对已 ok 的工作流重放 → 幂等 no-op                     │
                                                       ▼
                                                  ┌──────┐
                                                  │failed│
                                                  └──┬───┘
                                                     │
                                                     ▼  publish to DLQ
                                                  ┌──────┐
                                                  │ dead │ (人工介入)
                                                  └──────┘
```

## 4.3 用户账号状态

```
                ┌──────────┐
                │  active  │ ←────────────────┐
                └──┬───┬───┘                  │
      密码错 5 次 │   │  管理员停用            │
                  ▼   ▼                       │
             ┌──────┐ ┌──────────┐            │ admin unlock
             │locked│ │  disabled│            │
             └─┬────┘ └──────────┘            │
               │ 30 min 超时                  │
               └──────────────────────────────┘
```

---

# 第 5 部分：技术选型

| 层 | 选型 | 版本 | 理由 |
|---|---|---|---|
| **语言** | Python | 3.12 | 异步生态成熟；LLM SDK 全覆盖；团队熟悉 |
| **Web 框架** | FastAPI + Uvicorn (uvloop) | ≥0.115 | 异步原生、Pydantic 集成、OpenAPI 自动生成 |
| **ORM** | SQLAlchemy 2.0 async + aiomysql | ≥2.0.30 | 事务控制精细；显式 async；与 alembic 兼容 |
| **迁移** | alembic | ≥1.13 | 工业标准 |
| **缓存/队列** | Redis 7 + redis.asyncio | ≥5.0 | Streams 提供消费者组和 at-least-once；轻运维 |
| **向量库** | Milvus | ≥2.4 | 高性能 ANN；支持水平扩展；开源且企业部署友好 |
| **对象存储** | MinIO（或 S3 兼容） | ≥2024 | S3 协议；企业内可自托管 |
| **调度** | APScheduler | ≥3.10 | 嵌入主进程；相比独立调度简化部署 |
| **鉴权** | PyJWT + passlib[bcrypt] + ldap3 + authlib | 稳定版 | JWT（RS256/HS256）+ 本地 + LDAP + OIDC |
| **LLM SDKs** | openai + anthropic + google-generativeai | 最新 | 官方 SDK，多 Provider 网关通过统一接口包装 |
| **前端** | React + Vite + TypeScript | React 18+ | 主流选型，工程链成熟 |
| **反向代理** | nginx-unprivileged | 1.27-alpine | 非 root 镜像，UID 101，监听 8080 |
| **容器运行时** | containerd via K8s | — | 标准 |
| **编排** | Kubernetes + Helm | ≥1.27 / ≥3.12 | 企业标准 |
| **Ingress** | ingress-nginx + cert-manager | 稳定版 | TLS 自动签发 |
| **观测** | Prometheus + Grafana + Loki + OTel | 最新 | 三驾马车 + trace |
| **CI/CD** | GitHub Actions + Trivy + Syft + Cosign | 最新 | 安全供应链 |
| **容器加固** | PodSecurity Restricted + OPA Gatekeeper (可选) + Falco (可选) | — | 深度防御 |

---

# 第 6 部分：LLM 统一网关

## 6.1 设计目标

| 目标 | 实现 |
|---|---|
| 一套 API 覆盖多 Provider | 统一 `chat_completion / embedding / stream_completion / structured_output` 接口 |
| 故障自动回退 | primary → secondary → cloud fallback 三级 |
| 防止单 Provider 拖垮整个系统 | 每 provider 独立 CircuitBreaker |
| 云端调用合规 | 出云前正则+白名单脱敏，返回时反向还原 |
| 成本可见 | 每次调用写 `llm_call_log`（tokens / duration / cost） |
| 模型切换零停机 | `config/llm_gateway.yaml` 热加载，默认模型与 failover chain 可在线调整 |

## 6.2 架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                        LLM Gateway                                │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   统一调用接口                                │ │
│  │  chat_completion(msgs, model=?, purpose=?) → LLMResponse    │ │
│  │  embedding(texts) → list[vector]                            │ │
│  │  stream_completion(msgs, …) → AsyncIterator[str]            │ │
│  │  structured_output(schema, prompt) → dict (JSON mode)       │ │
│  └───────────────────────┬─────────────────────────────────────┘ │
│                           │                                       │
│  ┌─────────────────────────┼──────────────────────────────────┐  │
│  │  Router (按 purpose/model 选 provider + failover chain)    │  │
│  └──┬──────────────┬──────────────┬─────────────────┬────────┘  │
│     ▼              ▼              ▼                 ▼            │
│  ┌──────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │Local │  │ Anthropic  │  │  Google    │  │   OpenAI   │       │
│  │(vLLM)│  │  (Claude)  │  │  (Gemini)  │  │   (GPT)    │       │
│  │Deep- │  │            │  │            │  │            │       │
│  │Seek/ │  │            │  │            │  │            │       │
│  │Qwen/ │  │            │  │            │  │            │       │
│  │GLM   │  │            │  │            │  │            │       │
│  └──────┘  └────────────┘  └────────────┘  └────────────┘       │
│     │            │              │                 │             │
│     └────┬───────┴──────┬──────┴──────┬────────────┘             │
│          │              │             │                          │
│       内网直连      经出口代理 + 脱敏    经出口代理 + 脱敏           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │       横切：CircuitBreaker / RateLimiter / RetryPolicy      │ │
│  │              Anonymizer / LLMCallLog / Cache                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## 6.3 熔断与失败链

```yaml
# config/llm_gateway.yaml（摘）
circuit_breaker:
  failure_threshold: 5          # 连续失败 5 次打开熔断
  recovery_timeout_sec: 60      # 60 秒后半开试探
  half_open_probes: 2           # 成功 2 次后关闭

failover:
  classify_intel:   [deepseek-r1, qwen-72b,     gemini-pro]
  extract_ioc:      [deepseek-r1, qwen-72b,     claude-sonnet]
  score_intel:      [qwen-72b,    deepseek-r1]
  write_report:     [gemini-pro,  claude-sonnet, gpt-4o]
```

调用时传 `purpose="classify_intel"`，Gateway 按 failover chain 顺序尝试，失败时换下一个。

## 6.4 云端脱敏

```
出云前（对 provider in [anthropic,google,openai]）:
  1. 扫描 prompt 和 messages, 按以下规则替换:
     - 内部 IP 10.*/172.16-31.*/192.168.*  → <REDACTED_IP_{n}>
     - 员工姓名白名单匹配                   → <REDACTED_EMPLOYEE_{n}>
     - 企业内部域名 *.corp                 → <REDACTED_DOMAIN_{n}>
     - 企业资产 ID 模式                    → <REDACTED_ASSET_{n}>
  2. 保存 n → 真实值 映射 (仅在本次请求上下文)
  3. 发送替换后的内容到云端 LLM

收到响应后:
  1. 对响应文本做反向替换 <REDACTED_IP_1> → 真实 IP
  2. 若响应包含新产生的 <REDACTED_*_{n}>（LLM 引用），保留不还原（防信息泄露）
```

# 第 7 部分：工作流引擎

原生 Python 工作流引擎（`sia.gateway.workflow`）承载"情报采集 → 分析 → 报告"的编排。不依赖 Dify、Airflow、Prefect 等外部组件，因为：

- 工作流结构稳定（分析链路几乎不变）
- 需要嵌入到 FastAPI / consumer 进程中，减少跨进程调用
- YAML 版本控制 + 原生 Python step 执行器更利于单测

**工作流声明（`workflows/*.yaml`）**：

```yaml
# workflows/analyze_intel.yaml
id: analyze_intel
version: 1
inputs:
  input: dict

steps:
  classify:
    type: llm_call
    prompt: classify_intel     # 对应 prompts/classify_intel.yaml
    model_purpose: classify_intel
    inputs:
      content: "{{ input.content }}"
      title:   "{{ input.title }}"
    timeout_sec: 30

  extract_ioc:
    type: llm_call
    prompt: extract_ioc
    model_purpose: extract_ioc
    depends_on: [classify]
    inputs:
      content: "{{ input.content }}"

  score:
    type: python_func
    func: sia.analyzer.scorer:compute_total_score
    depends_on: [classify]
    inputs:
      classification: "{{ steps.classify.output }}"

  persist:
    type: python_func
    func: sia.analyzer.pipeline:persist_analysis_result
    depends_on: [score, extract_ioc]
    inputs:
      intel_id:       "{{ input.intel_id }}"
      classification: "{{ steps.classify.output }}"
      scores:         "{{ steps.score.output }}"
      iocs:           "{{ steps.extract_ioc.output.iocs }}"
```

**引擎保证**：
- 拓扑排序 steps；step 失败不影响其同层兄弟，但阻断后代
- 每 step 有独立 timeout / retry 配置
- step 执行记录写 `workflow_run` 表（执行历史 + 失败堆栈），查询便利
- 支持热加载：修改 YAML + 发送 SIGHUP（或通过 watchdog 监听 workflows/ 目录变化）

# 第 8 部分：数据架构

## 8.1 ER 图

```
                       ┌─────────────────────┐
                       │        user          │
                       │ id PK                │
                       │ username UNIQUE     │
                       │ email                │
                       │ role ENUM           │
                       │ auth_provider        │
                       │ external_id UNIQUE  │
                       │ hashed_password      │
                       │ status ENUM         │
                       │ failed_login_count   │
                       │ locked_until         │
                       │ last_login_at        │
                       └───────┬──────────────┘
                               │ 1..N
                               ▼
                       ┌─────────────────────┐
                       │    refresh_token     │
                       │ id PK                │
                       │ user_id FK           │
                       │ token_hash UNIQUE   │
                       │ expires_at           │
                       │ revoked              │
                       └─────────────────────┘

 ┌────────────────────┐                         ┌──────────────────────┐
 │      source         │                         │     intelligence      │
 │ id PK                │ 1                 N    │ id PK                 │
 │ name                 │◀───────────────────────│ source_id FK          │
 │ type ENUM (rss/api..)│                        │ title / content       │
 │ url                  │                        │ fingerprint UNIQUE   │
 │ config JSON          │                        │ cve_id                │
 │ enabled              │                        │ cvss_score / epss     │
 │ last_fetched_at      │                        │ priority_level ENUM   │
 │ failure_count        │                        │ total_score           │
 └──────────────────────┘                        │ primary_category      │
                                                 │ status ENUM           │
                                                 │ created_at            │
                                                 └──────┬───────────────┘
                                                        │
                    ┌───────────────────────────────────┼────────────────────┐
                    │1..N                               │1..1                 │0..N
                    ▼                                   ▼                     ▼
          ┌─────────────────────┐          ┌─────────────────────┐  ┌────────────────────┐
          │ intelligence_ioc     │          │   llm_analysis       │  │     report_item     │
          │ id PK                │          │ intel_id PK FK       │  │ id PK               │
          │ intel_id FK          │          │ summary              │  │ report_id FK        │
          │ type ENUM            │          │ impact_assessment    │  │ intel_id FK         │
          │ value                │          │ recommended_action   │  │ position            │
          │ confidence           │          │ mitre_techniques JSON│  └─────────┬──────────┘
          │ first_seen           │          │ llm_model_used       │            │
          └──────────────────────┘          │ token_count          │            │ N
                                            └──────────────────────┘            │
                                                                                │ 1
                                                                                ▼
                                                                      ┌────────────────┐
                                                                      │     report      │
                                                                      │ id PK           │
                                                                      │ type (daily/…)  │
                                                                      │ period_start    │
                                                                      │ period_end      │
                                                                      │ pdf_object_key  │
                                                                      │ generated_at    │
                                                                      └────────────────┘

                                    ┌─────────────────────┐
                                    │      outbox          │
                                    │ id PK                │
                                    │ event                │
                                    │ payload JSON         │
                                    │ status ENUM          │
                                    │ created_at           │
                                    │ sent_at              │
                                    └─────────────────────┘

                                    ┌─────────────────────┐
                                    │    llm_call_log     │
                                    │ id PK                │
                                    │ request_id           │
                                    │ provider / model     │
                                    │ purpose              │
                                    │ input_tokens         │
                                    │ output_tokens        │
                                    │ duration_ms          │
                                    │ success              │
                                    │ created_at           │
                                    └─────────────────────┘

                                    ┌─────────────────────┐
                                    │     audit_log        │
                                    │ id PK                │
                                    │ actor_id / actor_name│
                                    │ event                │
                                    │ target / target_id   │
                                    │ result               │
                                    │ ip / ua / method/path│
                                    │ ts                    │
                                    └─────────────────────┘
```

## 8.2 关键表结构

保留 v4.0 schema 主体（见 `src/sia/models/`）。v5.0 关键新增或调整：

```sql
-- status 增加 'suppressed'（误报抑制）与 'reviewed'（分析师确认）
ALTER TABLE intelligence MODIFY status
  ENUM('pending', 'analyzing', 'analyzed', 'emergency_dispatched',
       'reviewed', 'suppressed', 'archived', 'dlq') DEFAULT 'pending';

-- outbox 表（支持 Outbox Pattern 最终一致）
CREATE TABLE outbox (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    event       VARCHAR(64) NOT NULL,
    payload     JSON NOT NULL,
    status      ENUM('pending', 'sent', 'failed') DEFAULT 'pending',
    retry_count INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at     TIMESTAMP NULL,
    INDEX idx_status_created (status, created_at)
);

-- audit_log（v4.0 中是 append-only 表；v5.0 新增独立 logger 路径）
CREATE TABLE audit_log (
    id         BIGINT PRIMARY KEY AUTO_INCREMENT,
    ts         TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3),
    actor_id   BIGINT,
    actor_name VARCHAR(200),
    event      VARCHAR(64) NOT NULL,
    target     VARCHAR(64),
    target_id  VARCHAR(128),
    result     ENUM('success', 'failure', 'denied') DEFAULT 'success',
    ip         VARCHAR(45),
    method     VARCHAR(10),
    path       VARCHAR(500),
    ua         VARCHAR(200),
    extra      JSON,
    INDEX idx_actor_ts (actor_id, ts),
    INDEX idx_event_ts (event, ts)
);
```

## 8.3 向量库设计

Milvus 集合 `intel_vectors`：

| 字段 | 类型 | 索引 |
|---|---|---|
| `id` | INT64 | Primary |
| `intel_id` | INT64 | Scalar |
| `vector` | FLOAT_VECTOR(768) | IVF_FLAT (nlist=1024) |
| `created_at` | INT64 | Scalar |

使用场景：
- 去重：KNN top-5 + cosine > 0.9 判为重复
- 检索："相关情报"推荐
- 演化：Phase 3 可引入 HNSW 索引进一步提升召回

## 8.4 数据生命周期

| 数据 | 热 | 温 | 冷 | 删除 |
|---|---|---|---|---|
| intelligence | MySQL 实时 | 90 天内在 OLAP 副本 | >90 天压缩存 OSS | >7 年删除 |
| llm_call_log | 30 天 MySQL | 按月 partition, 压缩 | >1 年导 OSS | >5 年删除 |
| audit_log | 180 天 MySQL | >180 天 partition | >1 年 OSS (WORM) | 合规要求，永不删除（或按企业合规周期） |
| report (PDF) | MinIO 版本控制 | — | — | >2 年按类型删 |
| refresh_token | 7 天有效，过期后自动归档 + 30 天后硬删 | — | — | — |

---

# 第 9 部分：部署架构（0.2.0）

## 9.1 K8s 拓扑

```
┌───────────────────────────────────────────────────────────────────────┐
│                   K8s Cluster (企业私有云)                              │
│                                                                       │
│  Namespace: sia                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │  ┌─ Ingress ─────────────────────────────────────────────────┐   │  │
│  │  │ ingress-nginx + cert-manager (sia-ingress)                │   │  │
│  │  │   host: <INGRESS_HOST>                                    │   │  │
│  │  │   TLS: cert-manager / ClusterIssuer                       │   │  │
│  │  └──────────────┬───────────────────────────────┬────────────┘   │  │
│  │                 │ / (SPA)                       │ /api/ (API)    │  │
│  │  ┌──────────────▼─────────────┐  ┌──────────────▼─────────────┐  │  │
│  │  │ Service sia-web :80         │  │ Service sia-api :8080     │  │  │
│  │  │   → targetPort: http(8080)  │  │                            │  │  │
│  │  └──────────────┬──────────────┘  └──────────────┬────────────┘  │  │
│  │                 │                                 │                │  │
│  │  ┌──────────────▼─────────────┐  ┌──────────────▼─────────────┐  │  │
│  │  │ Deployment sia-web         │  │ Deployment sia-api         │  │  │
│  │  │   replicas: 2              │  │   replicas: 2 (HPA 2→8)    │  │  │
│  │  │   image: sia-web:0.2.0     │  │   image: sia-backend:0.2.0 │  │  │
│  │  │   UID: 101 (nginx unpriv)  │  │   UID: 1000                │  │  │
│  │  │   port: 8080               │  │   port: 8080               │  │  │
│  │  │   readOnlyRootFS: true     │  │   readOnlyRootFS: true     │  │  │
│  │  │   drop: [ALL]              │  │   drop: [ALL]              │  │  │
│  │  │   seccomp: RuntimeDefault  │  │   seccomp: RuntimeDefault  │  │  │
│  │  │   topologySpread:          │  │   topologySpread:          │  │  │
│  │  │     hostname + zone        │  │     hostname + zone        │  │  │
│  │  └─────────────────────────────┘  └──────────────┬─────────────┘  │  │
│  │                                                   │                │  │
│  │                                                   │ Redis Streams  │  │
│  │                                                   │ (XADD / XREAD) │  │
│  │                                                   ▼                │  │
│  │                                   ┌─────────────────────────────┐  │  │
│  │                                   │ Deployment sia-consumer     │  │  │
│  │                                   │   replicas: 1+              │  │  │
│  │                                   │   image: sia-backend:0.2.0  │  │  │
│  │                                   │   UID: 1000                 │  │  │
│  │                                   │   (no service — pull-only)  │  │  │
│  │                                   │   readOnlyRootFS + drop ALL │  │  │
│  │                                   │   terminationGracePeriod 90s│  │  │
│  │                                   └─────────────────────────────┘  │  │
│  │                                                                     │  │
│  │  ┌─ ConfigMap sia-config ────────────────────────────────────────┐ │  │
│  │  │   SIA_ENV, SIA_MYSQL_HOST/PORT/USER/DATABASE/POOL/TLS_MODE,   │ │  │
│  │  │   SIA_REDIS_HOST/PORT/DB/TLS_*, SIA_MILVUS_*, SIA_MINIO_*,    │ │  │
│  │  │   SIA_AUTH_JWT_ALGORITHM, SIA_OTLP_ENDPOINT, SIA_LOG_*        │ │  │
│  │  └────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                     │  │
│  │  ┌─ Secret sia-secrets (mode 0400, mounted file /etc/sia/secrets)─┐ │  │
│  │  │   SIA_AUTH_JWT_SECRET / JWT_PRIVATE_KEY / JWT_PUBLIC_KEY       │ │  │
│  │  │   SIA_API_KEY / SIA_ADMIN_PASSWORD                             │ │  │
│  │  │   SIA_MYSQL_PASSWORD / SIA_REDIS_PASSWORD                      │ │  │
│  │  │   SIA_MINIO_ACCESS_KEY / SIA_MINIO_SECRET_KEY                  │ │  │
│  │  │   SIA_MILVUS_TOKEN                                             │ │  │
│  │  │   SIA_GOOGLE_API_KEY / SIA_ANTHROPIC_API_KEY / SIA_OPENAI_…    │ │  │
│  │  └────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                     │  │
│  │  ┌─ NetworkPolicy sia-network-policy ────────────────────────────┐ │  │
│  │  │  Ingress: allow ingress-nginx → :8080                          │ │  │
│  │  │           allow 同 app.kubernetes.io/name=sia 内部               │ │  │
│  │  │  Egress:  DNS (:53)                                             │ │  │
│  │  │           MySQL (:3306) / Redis (:6379) / Milvus (:19530) /    │ │  │
│  │  │           MinIO (:9000)                                         │ │  │
│  │  │           HTTPS/HTTP :443/:80 限于 network.egressAllowedCidrs  │ │  │
│  │  └────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                     │  │
│  │  ┌─ Jobs (post-install) ─────────────────────────────────────────┐ │  │
│  │  │   sia-db-init-<rev>  (alembic upgrade head)                    │ │  │
│  │  │   sia-db-seed-<rev>  (首次创建 admin + 默认源 + 评分策略)      │ │  │
│  │  └────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                     │  │
│  │  ┌─ PodDisruptionBudget sia-api-pdb: minAvailable: 1 ─────────────┐ │  │
│  │  └─ HorizontalPodAutoscaler sia-api-hpa: 2→8 @ 70%CPU ────────────┘ │  │
│  │                                                                     │  │
│  │  可选: Falco rules ConfigMap / Gatekeeper Constraints              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  Namespace: observability (既有)                                         │
│     Prometheus (ServiceMonitor 拉 sia-api:/metrics)                    │
│     Grafana / Loki / OTel Collector                                    │
└───────────────────────────────────────────────────────────────────────┘

外部（由平台团队托管）:
  MySQL 8.0 (TLS required, CA Secret mysql-ca 挂载到 /etc/sia/tls/mysql/)
  Redis 7   (TLS rediss://, CA Secret redis-ca)
  Milvus 2.4
  MinIO (S3 兼容)
  企业出口代理  (LLM / RSS / NVD 调用必经)
  企业 LLM 服务 (vLLM/Ollama)
  SMTP / IM Webhook
```

## 9.2 网络架构

```
                   互联网
                     │
                     ▼
                企业防火墙
                     │
           ┌─────────┴──────────┐
           │  Ingress Controller │  (ingress-nginx)
           │  + cert-manager    │
           └─────────┬──────────┘
                     │ TLS 1.2+
        ┌────────────┼─────────────┐
        │ /          │ /api/       │
        ▼            ▼             │
   ┌─────────┐   ┌─────────┐       │
   │ sia-web │   │ sia-api │       │
   │ :8080   │   │ :8080   │       │
   └─────────┘   └─┬───────┘       │
       │           │                │
       └──proxy────┘ (同 NS Service)│
                   │                │
                   │ (consumer/api  │
                   │  共用同套 ext  │
                   │  依赖)         │
                   ▼                │
   ┌──────────────────────────────────────────┐
   │ 外部数据层（企业托管，非 sia NS）         │
   │   MySQL (TLS 3306) / Redis (TLS 6379)    │
   │   Milvus (19530) / MinIO (TLS 9000)      │
   └──────────────────────────────────────────┘

   ┌──────────────────────────────────────────┐
   │ 企业 LLM 服务 (内网)                       │
   │   vLLM/Ollama (OpenAI 兼容 API)           │
   └──────────────────────────────────────────┘

   ┌──────────────────────────────────────────┐
   │ 企业出口代理 (Squid/Nginx forward)        │
   │   LLM 云 API / RSS / NVD / CISA           │
   │   审计 + 域名白名单 + mTLS 到代理         │
   └──────────────────────────────────────────┘
```

NetworkPolicy 默认拒绝，逐项白名单（见 §9.1 图内细节）。出口的 443/80 由 `network.egressAllowedCidrs` 参数化，严格环境可收紧到代理的 IP。

## 9.3 集中化配置与一键部署

```
 Operator          deployment.config.yaml        configure.sh
    │                       │                         │
    │                       │                         │
    │── cp .example → .yaml                           │
    │── edit (填占位符)     │                         │
    │                       │                         │
    │── ./configure.sh --generate-secrets ───────────▶│
    │                       │                         │
    │                       │  校验必填项 (K8S_CONTEXT, REGISTRY_URL, …)
    │                       │  校验 Secret 强度
    │                       │  对空字段:
    │                       │    openssl rand -hex 32      (JWT / API key)
    │                       │    openssl rand -base64 24   (admin password)
    │                       │    openssl genpkey RSA 3072  (JWT RS256 keypair)
    │                       │  回写 deployment.config.yaml (600)
    │                       │  渲染 deploy/helm/sia/values-prod.yaml
    │                       │  渲染 deploy/rendered/sia-secrets.yaml (600)
    │                       │
    │── ./deploy-k8s.sh ───▶│
    │                       │  docker build sia-backend:<TAG>
    │                       │  docker build sia-web:<TAG>
    │                       │  docker push <REGISTRY>/...
    │                       │  kubectl create ns sia --dry-run=client | apply
    │                       │  kubectl apply -f deploy/rendered/sia-secrets.yaml
    │                       │  helm upgrade --install sia deploy/helm/sia \
    │                       │    -f deploy/helm/sia/values-prod.yaml \
    │                       │    --set api.image.tag=<TAG> ...
    │                       │    --wait --timeout 5m
    │                       │  kubectl rollout status deploy/sia-api
    │                       │  冒烟测试:
    │                       │    curl /api/v1/health → 200
    │                       │    curl /api/v1/intelligence (无 auth) → 401
    │                       │
    ▼                       ▼
 部署完成 + 冒烟通过
```

## 9.4 滚动更新与金丝雀

- **滚动**：所有 Deployment `strategy.rollingUpdate: {maxSurge:1, maxUnavailable:0}`；配合 readiness probe、PDB (minAvailable:1)，零停机
- **优雅关停**：`terminationGracePeriodSeconds: 30` (api/web) / 90 (consumer)；`preStop hook sleep 5` 等 Service 端点摘除后再停
- **金丝雀**：通过 ingress-nginx `nginx.ingress.kubernetes.io/canary: "true"` 注解做 5% → 20% → 50% → 100% 分阶段发布（配置在 `deployment.config.yaml` 的 `ingress.canary` 章节，当前未默认开启）

---

# 第 10 部分：安全模型

## 10.1 威胁建模（带信任边界的 DFD）

```
           ┌──────────────────────────── 信任边界 A (互联网) ─────────────────────────┐
           │                                                                          │
           │   情报源 (RSS/NVD/CISA/公众号/暗网)                                      │
           │   云端 LLM (Anthropic/Google/OpenAI)                                     │
           │                                                                          │
           └────────────┬─────────────────────────────┬─────────────────────────────┘
                         │ (HTTPS + 出口代理审计)      │
                         ▼                              ▲
           ┌──────── 信任边界 B (企业 DMZ / Ingress) ────────────────────────────┐
           │                                                                     │
           │    Ingress-nginx (TLS 终止, WAF 可选)                                │
           │                                                                     │
           └────────────┬─────────────────────────────┬─────────────────────────┘
                         │                              │
                         ▼                              ▲
           ┌──────── 信任边界 C (Pod 应用运行时) ─────────────────────────────────┐
           │                                                                     │
           │   sia-web → sia-api → sia-consumer                                  │
           │   (readOnlyRootFS + drop:[ALL] + seccomp RuntimeDefault)            │
           │                                                                     │
           │   Secret 仅以文件挂载 /etc/sia/secrets/ 读取                         │
           │                                                                     │
           └────────────┬─────────────────────────────┬─────────────────────────┘
                         │ (NetworkPolicy 白名单)       │
                         ▼                              ▲
           ┌──────── 信任边界 D (企业内网托管数据层) ───────────────────────────────┐
           │                                                                      │
           │   MySQL (TLS required) / Redis (TLS) / Milvus / MinIO                │
           │   企业 LLM (vLLM)                                                     │
           │                                                                      │
           └──────────────────────────────────────────────────────────────────────┘

STRIDE 映射到信任边界:
  边界 A → B: Spoofing (伪造情报源) / Information disclosure (云 LLM 回流)
    → 白名单 + 出口代理审计 + 出云前脱敏
  边界 B → C: DoS / Injection
    → 限流 (分层) + WAF + pydantic 严格校验
  边界 C 内部: Tampering / Elevation of Privilege
    → RBAC + 审计 + readOnlyRootFS + Pod Security Restricted
  边界 C → D: Information disclosure (数据库泄密) / Tampering
    → TLS + 最小权限 (DB user 只有 sia schema)
  其他: Repudiation → 独立 audit logger 永久保存
```

## 10.2 20 项加固基线

| ID | 级别 | 要求 | 落点 | 验收 |
|---|---|---|---|---|
| SEC-001 | 🔴 | 无默认 JWT 密钥 | `config.py::AuthSecretSettings` 生产强校验 | 置空 SIA_AUTH_JWT_SECRET → 启动崩溃 |
| SEC-002 | 🔴 | 无默认 DB 密码 | `DatabaseSettings` + `.env.example` + `docker-compose.yaml` 全无默认 | 同上 |
| SEC-003 | 🟠 | 无默认 MinIO 凭据 | `MinIOSettings` 拒绝 `minioadmin` | 同上 |
| SEC-004 | 🟡 | 生产禁 debug | `Settings._validate_env` 拒绝 prod+debug | rendered ConfigMap: SIA_DEBUG=false |
| SEC-005 | 🟠 | API Key 不 log | `rbac.py` constant-time + redaction filter | grep 日志无 X-API-Key 值 |
| SEC-006 | 🟡 | 按身份限流 | `RateLimitMiddleware` 以 JWT/API-Key/IP 三层 | 32 请求/min 后 429 |
| SEC-007 | 🟡 | TLS 到 DB/Redis | connect_args + rediss:// + CA Secret 挂载 | 关闭 CA 挂载 → TLS 握手失败 |
| SEC-008 | 🟡 | Secret 作为文件 | `/etc/sia/secrets/` + SIA_SECRETS_DIR | `kubectl exec -- env` 无 _PASSWORD |
| SEC-009 | 🟡 | 容器加固 | helper `sia.containerSecurityContext` 全部 Deploy | helm render: readOnlyRootFS true ≥5 次 |
| SEC-010 | 🟡 | nginx 非 root | nginx-unprivileged + :8080 | kubectl exec sia-web -- id → uid=101 |
| SEC-011 | 🟡 | 镜像供应链 | Trivy + Syft + Cosign keyless | CI 含 3 个 job 成功 |
| SEC-012 | 🟡 | 集群级防护 | Falco 规则 + Gatekeeper 样板 | 手工启用后无 violation |
| SEC-013 | 🟡 | 审计 | `sia.common.audit` 独立 logger | 登录一次即可见 JSON 事件 |
| SEC-014 | 🟡 | RS256 | configure.sh 自动生成 keypair | rendered ConfigMap: jwtAlgorithm RS256 |
| SEC-015 | 🟡 | 登录独立限流 | 5 req/min/IP 桶 | 6 次 login 第 6 次 429 |
| SEC-016 | 🟢 | 日志脱敏 | `install_redaction` 挂根 + sqlalchemy + httpx | debug 模式 URL 内密码被 *** |
| SEC-017 | 🟢 | 依赖更新 | dependabot + pip-audit CI | 仓库含 .github/dependabot.yml |
| SEC-018 | 🟢 | 消费者优雅退出 | SIGTERM → stop_event | `kubectl delete pod` 日志见 "exited cleanly" |
| SEC-019 | 🟢 | 跨节点散布 | topologySpreadConstraints | 多 pod 分散在不同 node |
| SEC-020 | 🟢 | 出口 CIDR | network.egressAllowedCidrs 可收紧 | 收紧后非白名单外部连接被 deny |

## 10.3 密钥管理

- **生成**：`configure.sh --generate-secrets` 使用 `openssl rand -hex 32` 或 3072-bit RSA keypair
- **存储**：生产环境通过 sealed-secrets / External Secrets Operator / Vault Agent 与企业机密仓同步，SIA 应用只从 `/etc/sia/secrets/` 读；`deploy/rendered/sia-secrets.yaml` 仅为 bootstrap 辅助
- **分级**：P0（JWT 私钥 / DB root / API key）/ P1（MinIO / Milvus / LLM provider）/ P2（非密配置）
- **轮换 SOP**：见 §3.4；建议 JWT 90 天，数据库密码随外部 DB 的策略，API Key 半年
- **访问审计**：所有通过 K8s API 读 Secret 的操作由 K8s audit 记录；应用内部读取不需额外审计

## 10.4 审计与合规

`sia.audit` logger 事件清单（随实现扩展）：

| event | 触发点 | 必要字段 |
|---|---|---|
| `user.login` | /auth/login | actor_id, actor_name, result, ip, provider |
| `user.logout` | /auth/logout | actor_id, actor_name, ip |
| `user.lockout` | 锁定触发 | actor_id, failed_count |
| `user.password_change` | 改密 | actor_id |
| `admin.user.create/update/delete` | /users | actor_id, target_id |
| `admin.source.create/update/delete` | /sources | actor_id, target_id |
| `intel.export` | CSV/JSON 导出 | actor_id, count, filter |
| `report.export` | 下载 PDF | actor_id, report_id |
| `config.change` | 配置变更 | actor_id, diff |

合规映射：

| 框架 | 对应控制 |
|---|---|
| 等保 2.0 "身份鉴别" | 本地 + LDAP + OIDC + 账号锁定 + RS256 JWT |
| ISO 27001 A.12.4 "日志与监视" | sia.audit + Prometheus + OTel |
| GDPR Art. 32 | TLS 全链路 + Secret-as-file + 出云脱敏 |
| SOC 2 "最小权限" | RBAC + NetworkPolicy + drop:[ALL] |
| PCI-DSS 6.5 | SQL 参数绑定 + pydantic + redaction |

---

# 第 11 部分：非功能需求（NFR）

见附录 B 详表。摘要：

| 类别 | 关键指标 | 目标 |
|---|---|---|
| 可用性 | API 月度可用性 | ≥ 99.5% |
| 性能 | 情报列表 P95 延迟 | ≤ 500 ms |
| 性能 | LLM 分析单次 P95 | ≤ 30 s |
| 吞吐 | 每日分析情报量 | ≥ 1000 条 |
| RTO | 故障恢复时间 | ≤ 30 min |
| RPO | 数据丢失窗口 | ≤ 5 min（依赖 MySQL binlog） |
| 扩展性 | 水平扩展 API | 2 → 8 (HPA) |
| 可观测 | 关键指标覆盖率 | 100% 关键路径有 metric + trace |

---

# 第 12 部分：可观测性

### 12.1 日志

- 格式：JSON，字段 `ts, level, logger, msg, trace_id, span_id`
- 路由：
  - `sia.*` 应用日志 → 标准输出 → Loki
  - `sia.audit` 审计日志 → 同时标准输出 + 写 MySQL `audit_log` 表（双通道）
  - SQLAlchemy / httpx / uvicorn 已挂 redaction filter
- 保留：Loki 30 天热存；审计表 180 天热，>180 天归档

### 12.2 指标

Prometheus 暴露 `/metrics`：

| 指标 | 类型 | 含义 |
|---|---|---|
| `sia_http_requests_total{method,route,code}` | Counter | API 请求计数 |
| `sia_http_request_duration_seconds{route}` | Histogram | API 延迟 |
| `sia_llm_call_total{provider,model,purpose,result}` | Counter | LLM 调用 |
| `sia_llm_tokens_total{provider,model,direction}` | Counter | Token 用量 |
| `sia_workflow_step_duration_seconds{workflow,step}` | Histogram | 工作流 step 延迟 |
| `sia_redis_stream_pending{stream,group}` | Gauge | 未 ACK 消息数 |
| `sia_redis_stream_dlq{stream}` | Counter | DLQ 计数 |

### 12.3 Tracing

OpenTelemetry SDK 自动 instrumentation（FastAPI + SQLAlchemy + httpx + redis）；OTLP 出口指向 `$SIA_OTLP_ENDPOINT`（若设置）。

### 12.4 告警

| 告警 | 阈值 | 动作 |
|---|---|---|
| API 5xx 率 > 1% / 5 min | PagerDuty P2 |
| HPA 顶到 maxReplicas 持续 10 min | P3 容量告警 |
| Stream pending > 1000 | P3 消费者滞后 |
| DLQ 任何消息 | P3 毒消息 |
| 登录失败 > 20 / 5 min 从同 IP | P2 暴破嫌疑 |
| 证书 30 天内到期 | P4 提醒 |

---

# 第 13 部分：可运维性

- **配置变更**：编辑 `deployment.config.yaml` → `configure.sh` → `deploy-k8s.sh --skip-build --skip-push` → `rollout restart`
- **版本升级**：`deploy-k8s.sh -t v0.x.y --skip-build --skip-push`；alembic 迁移自动运行（post-install hook）
- **回滚**：`helm rollback sia <rev> -n sia`；若含破坏性 schema 变更需先 `alembic downgrade`
- **备份恢复**：见 `docs/OPERATIONS_GUIDE.md` §6；DR 顺序 MySQL → Redis → Milvus → MinIO → SIA
- **Secret 轮换**：见 §3.4；推荐 External Secrets Operator

---

# 第 14 部分：测试策略

金字塔：

```
             ┌──────────────┐
             │   E2E (5%)    │  playwright + 真 K8s
             └──────────────┘
           ┌──────────────────┐
           │ Integration (15%) │  testcontainers (MySQL/Redis), LLM mock
           └──────────────────┘
       ┌──────────────────────────┐
       │     Unit (80%)            │  pytest, 无外部依赖
       └──────────────────────────┘
```

核心测试：
- **单测**：config 校验、rate_limit、audit、jwt HS/RS 互通、redaction、workflow engine、scorer
- **集成**：API 契约（schemathesis）、数据库迁移、Redis 消费者组可靠性
- **E2E**：登录→列表→查看→导出全链路
- **安全**：personal-info-lint、CI trivy HIGH+ 阻断、pip-audit
- **性能**：LLM Gateway 并发、MySQL 查询基准（pytest-benchmark）

---

# 第 15 部分：风险与应急（FMEA）

详表见附录 C。Top 5 风险：

1. 云端 LLM 不可用 / 配额耗尽 → 断路器 + 自动回退本地模型
2. 情报源被投毒（恶意 Prompt Injection 嵌入正文） → LLM 响应 JSON schema 严格校验；拒绝无法解析的输出；ATT&CK 映射不入库
3. 大量 P0 涌入导致推送风暴 → 每渠道限速 + 相同事件聚合推送
4. 数据库迁移失败导致滚动升级阻塞 → alembic downgrade + helm rollback + 维护窗口人工介入
5. 容器镜像供应链污染 → Trivy 每次 CI 扫 + Cosign 验签 + Gatekeeper 拒绝未签名镜像

---

# 第 16 部分：实施规划

| 阶段 | 里程碑 | 时间窗 | 验收 |
|---|---|---|---|
| Phase 0 | 设计冻结 + 环境就绪 | W1-W2 | 本设计 v5.0 评审通过，K8s + 数据层就绪 |
| Phase 1 | 核心功能 MVP | W3-W6 | 单源（NVD）采集→分析→入库→基础 Web |
| Phase 2 | 多源 + 报告 | W7-W9 | RSS/CISA/公众号接入；日报/周报生成 |
| Phase 3 | 紧急预警 + 集成 | W10-W11 | P0 邮件+IM 推送；API 对外；LDAP/OIDC |
| Phase 4 | 安全加固 + 供应链 | W12-W13 | 20 项基线全部通过；CI 扫描全开；OPA 可选启用 |
| Phase 5 | 灾备 + 性能 | W14 | 演练 RTO/RPO；性能压测达 NFR |
| Phase 6 | 上线 | W15 | 生产环境发布 v0.2.0 |

---

# 附录 A：架构决策记录（ADR）

每条 ADR 格式：**标题 / 上下文 / 决策 / 理由 / 后果**。

### ADR-001：用原生 Python 工作流引擎，而非 Dify

- 上下文：v3.0 曾用 Dify 编排；v4.0 起改为原生。
- 决策：自研 `sia.gateway.workflow`，YAML 定义 + Python step 执行器。
- 理由：避免跨进程调用、可单测、工作流结构稳定不需要可视化 UI、减少运维组件。
- 后果：失去可视化编辑；团队需要自己维护引擎；换来 4-8 GB 内存节省 + 部署简化。

### ADR-002：LLM 多 Provider 统一网关

- 上下文：需要本地 + 云端兼用，且防止单 Provider 不可用拖垮系统。
- 决策：抽象 `LLMProvider` 基类 + Router + CircuitBreaker + Failover。
- 理由：Provider SDK 差异大（OpenAI 兼容 / Anthropic / Google），必须统一；熔断+回退提供韧性。
- 后果：每引入新 Provider 需实现 Provider 适配；换来架构可演进。

### ADR-003：Secret 仅以文件挂载，不注入环境变量

- 上下文：v4.0 envFrom secretRef；生产环境可能被 `kubectl describe pod` / ps / 调试日志泄露。
- 决策：Helm 挂 Secret 到 `/etc/sia/secrets/`，`defaultMode: 0400`；应用通过 `SIA_SECRETS_DIR` 读取。
- 理由：最小曝光面；file 权限可控；与 Vault Agent Injector 约定兼容。
- 后果：应用配置加载路径改为 file-first，env 兜底；文档需指引；运维习惯调整。

### ADR-004：JWT 默认算法 RS256（而非 HS256）

- 上下文：HS256 简单但私钥即验签密钥，泄露即全盘失守；RS256 支持公钥分发给下游服务验签。
- 决策：`configure.sh --generate-secrets` 默认生成 3072-bit RSA keypair；`jwtAlgorithm: RS256`。
- 理由：准备面向企业内部多服务生态的未来；公钥可公开。
- 后果：密钥对管理更复杂；保留 HS256 分支兼容已有部署。

### ADR-005：三个 Deployment，而非 v4.0 的六个服务

- 上下文：v4.0 设想微服务化；实际功能间共用大量代码（数据模型、LLM 网关、DB 会话）。
- 决策：合并为 `sia-api` / `sia-consumer` / `sia-web`；scheduler 嵌 api，collector/analyzer/reporter 嵌 consumer 的 workflow 执行器。
- 理由：减少进程间调用、运维对象、镜像数量；保留 `sia-api` 的横向扩展、consumer 单独扩。
- 后果：单镜像大小增加（但多架构构建共享层），Deployment 数量从 6 降到 3，Ingress/Secret/ConfigMap 复用。

### ADR-006：Outbox Pattern 做跨存储最终一致

- 上下文：业务写 MySQL 后，还要发 Redis Streams；"两阶段"方案过重。
- 决策：事务内同时写 `outbox` 表；独立发布者轮询搬到 Redis。
- 理由：单库事务天然原子；Redis 异步发布，失败可重试。
- 后果：outbox 表会增长，需定期清理；消息延迟约 100-500ms。

### ADR-007：Milvus 作为去重层，而非仅依赖 SHA1 指纹

- 上下文：同一情报不同来源会有措辞差异但语义相同。
- 决策：SHA1 指纹（strict 去重）+ Milvus KNN（模糊去重 > 0.9）。
- 理由：SHA1 只能抓字面重复；向量去重抓语义重复。
- 后果：引入 Milvus 依赖；换来更高质量的去重率。

### ADR-008：nginx-unprivileged + 监听 8080（而非 root nginx + :80）

- 上下文：v4.0 web Deployment 为运行 nginx 在 :80 采用 `runAsNonRoot: false`，与整体 Pod Security Restricted 政策冲突。
- 决策：改用 `nginxinc/nginx-unprivileged:1.27-alpine`，UID 101，:8080。
- 理由：容器内无需 CAP_NET_BIND_SERVICE；Service targetPort 映射保持对外 :80。
- 后果：升级基础镜像需跟随 nginx-unprivileged 发布节奏；零成本换来合规。

### ADR-009：限流按身份分桶 + 登录单独限流

- 上下文：按 IP 限流容易被共享出口（NAT / 代理）互相影响；按身份限流能更准识别滥用。
- 决策：默认桶按 JWT digest / API-Key digest / IP；登录端点额外 5 req/min/IP（桶独立）。
- 理由：精准、对合法用户友好；登录暴破有独立防线。
- 后果：无后端 session 存储，桶为 in-memory（多实例下每实例独立，短期流量可能突破限额 N 倍；可接受，严格场景可切 Redis 桶）。

### ADR-010：审计日志走独立 logger + 双通道落地

- 上下文：审计日志与业务日志混在一起不利于 SIEM 单独摄取。
- 决策：`sia.audit` logger 关闭 propagate，独立 handler；同时 INSERT 到 `audit_log` 表。
- 理由：SIEM 可按 logger 名过滤；DB 表支持细粒度查询；两通道互补。
- 后果：对性能影响微乎其微；极端情况（DB 挂）审计写仍有标准输出保底。

### ADR-011：出云 LLM 调用统一脱敏 + 反向还原

- 上下文：情报原文可能含企业内部 IP、员工名、资产名。
- 决策：LLM Gateway 识别 provider 类型，cloud 前走 `Anonymizer`；响应后按上下文映射还原。
- 理由：合规 + 最小化泄露；同时对业务层透明。
- 后果：新增规则需维护白名单；对极端情况（LLM 自己产生新的 `<REDACTED_*>` 占位）保守处理不还原。

### ADR-012：全量签名镜像 + SBOM 入 CI

- 上下文：供应链攻击渐成主流（SolarWinds、xz utils 等）。
- 决策：CI 在 push 后 Trivy HIGH+ 阻断；Syft 生成 CycloneDX SBOM；Cosign keyless 签名（GitHub OIDC → Fulcio + Rekor）。
- 理由：每版镜像可溯源；运行时 Gatekeeper 可校验签名。
- 后果：CI 时间 +2-3 min；企业内可替换 Fulcio 为内部 OIDC。

---

# 附录 B：NFR 指标详表

| 类别 | 指标 | 目标 | 度量方式 | 告警 |
|---|---|---|---|---|
| **可用性** | API 月度可用性 | ≥ 99.5% | Prometheus uptime / blackbox_exporter 外部探测 | 月度回溯 |
| 可用性 | P0 情报推送链路可用 | ≥ 99.9% (业务 SLA) | 内部 xpending + 发送成功率 | 实时 |
| **性能（延迟）** | `/api/v1/intelligence` P50/P95 | 100 ms / 500 ms | histogram_quantile | P95 >1s 持续 5min |
| 性能 | 登录 /auth/login P95 | ≤ 300 ms | 同上 | P95 >1s |
| 性能 | LLM 单次分析 P95 | ≤ 30 s | 工作流 step metric | >60s |
| 性能 | 报告 PDF 生成 P95 | ≤ 60 s | 报告生成 metric | — |
| **吞吐** | 日均情报入库 | ≥ 1000 条 | MySQL count / day | — |
| 吞吐 | 分析队列处理速率 | ≥ 50 条 / min | sia_workflow_step rate | stream pending > 1000 |
| **容量** | MySQL 存储 12 个月 | < 100 GB | 表大小 | 80% 预警 |
| 容量 | Milvus 向量条数 12 个月 | < 5M | Milvus count | — |
| 容量 | Redis 内存 | < 2 GB | INFO memory | 80% |
| **恢复** | RTO | ≤ 30 min | 演练测得 | — |
| 恢复 | RPO | ≤ 5 min | MySQL binlog 频率 | — |
| **扩展** | API Pod 自动扩展 | 2 → 8 @ CPU 70% | HPA | maxReplicas 打满 10min |
| **可观测** | 关键路径 trace 覆盖 | 100% | OTel exporter | 缺失 trace 连续 1 天 |
| 可观测 | 审计事件无丢失 | = 100% | 事件计数与业务操作计数比 | 不匹配告警 |
| **安全** | 20 项基线验收 | 100% | 部署后 checklist + CI lint | 任何项退步 |
| 安全 | CVE HIGH+ 修复 | ≤ 7 天 | Trivy CI | 超 SLA |

---

# 附录 C：FMEA 详表

| # | 失效模式 | 失效原因 | 影响 | 严重度 | 发生概率 | 可探测性 | RPN | 缓解 |
|---|---|---|---|---|---|---|---|---|
| 1 | 云端 LLM 不可用 | 配额 / 网络 / 服务故障 | 分析队列积压，无法生成报告 | 7 | 6 | 8 | **336** | 断路器 + 三级 failover 到本地模型 + 告警 |
| 2 | 情报源被投毒（Prompt Injection） | 攻击者向 RSS 提供恶意内容 | LLM 输出被劫持，错误分类 | 8 | 4 | 5 | **160** | 系统 prompt 不可替换；响应 JSON schema 严格校验；拒绝无法解析的输出 |
| 3 | MySQL 主节点故障 | 硬件 / 网络 | 写操作全部失败 | 9 | 3 | 9 | **243** | 主备切换 + binlog 重放；外部托管 DB 的 SLA |
| 4 | Redis Streams 堆积 | 消费者全挂或 LLM 慢 | P0 推送延迟 | 8 | 5 | 9 | **360** | HPA + 告警 pending > 1000；消费者优雅关停确保不丢消息 |
| 5 | Secret 泄露 | Git 意外提交 / 开发机被盗 | 凭据失效，潜在数据泄露 | 9 | 3 | 6 | **162** | Secret 仅文件挂载 + gitignored + personal-info-lint；立即轮换 SOP |
| 6 | 容器镜像供应链污染 | 基础镜像漏洞 / 恶意依赖 | RCE / 数据泄露 | 10 | 3 | 6 | **180** | Trivy CI 阻断 HIGH+；Cosign 签名 + Gatekeeper 校验 |
| 7 | 长时 LLM 调用占用资源 | 大 prompt + 慢模型 | API 线程池饥饿 | 6 | 5 | 7 | **210** | 超时限制 + RateLimit + 异步处理 |
| 8 | 大量报告推送 | P0 事件风暴 | SMTP / IM 配额耗尽 | 6 | 4 | 5 | **120** | 推送限速 + 相同事件聚合 |
| 9 | alembic 迁移失败 | Schema 冲突 / DDL 锁 | 部署阻塞 | 7 | 3 | 9 | **189** | 备份 + 蓝绿 DB 演练 + 迁移脚本 code review |
| 10 | 容器逃逸 | 内核 CVE + 权限配置漏洞 | 宿主入侵 | 10 | 2 | 4 | **80** | readOnlyRootFS + drop:[ALL] + seccomp + Falco 检测 |
| 11 | 审计日志篡改 | DB 权限 / 应用 bug | 合规不符 | 8 | 2 | 7 | **112** | `audit_log` 只 INSERT + SIEM 独立摄取；DB 用户只授 INSERT |
| 12 | DB/Redis 间网络闪断 | 网络抖动 | 短时请求失败 | 5 | 6 | 4 | **120** | 连接池重试 + health check + 线程回退 |
| 13 | LLM 返回格式异常 | 模型漂移 | 分析结果错误 | 6 | 5 | 6 | **180** | pydantic 严格校验；格式错误写 DLQ；人工回顾 |
| 14 | 存储配额耗尽 | 归档未及时 | 新写入失败 | 8 | 3 | 7 | **168** | 周 job 清理 outbox / llm_call_log 老数据；磁盘告警 |
| 15 | JWT 密钥暴露 | 日志泄露 / 误提交 | 所有 JWT 可伪造 | 9 | 2 | 5 | **90** | RS256（仅私钥签名）+ 文件挂载 + 日志脱敏 + 定期轮换 |

> RPN = 严重度 × 发生概率 × 可探测性（数字越大风险越高）；> 200 进入重点跟踪。

---

# 附录 D：v5.0 vs v4.0 差异总表

| 维度 | v4.0 | v5.0 |
|---|---|---|
| **部署形态** | 3 namespace (`sia-system` / `sia-data` / `sia-monitor`) | 单 `sia` NS，数据层外部托管 |
| **服务拆分** | 6 个 Deployment | 3 个 Deployment (`sia-api` / `sia-consumer` / `sia-web`) |
| **Secret 注入** | `envFrom: secretRef` | 文件挂载 `/etc/sia/secrets/`, mode 0400 |
| **容器加固** | `runAsNonRoot: true` | + `readOnlyRootFilesystem` + `drop:[ALL]` + seccomp + emptyDir for writable |
| **nginx** | 标准 nginx : 80 | nginx-unprivileged : 8080, UID 101 |
| **JWT** | HS256 默认 | RS256 默认 (HS256 保留兼容) |
| **限流** | 按 IP | 按 JWT/API-Key/IP 分桶 + 登录 5/min/IP 独立 |
| **TLS 到 DB** | 未明确 | mode=required, caSecretName 挂载 |
| **审计** | DB 表为主 | 独立 `sia.audit` logger + DB 双通道 |
| **日志** | 文本 | JSON 结构化 + redaction filter |
| **供应链** | Trivy | Trivy + Syft SBOM + Cosign keyless + dependabot + pip-audit |
| **配置入口** | values-prod-example.yaml + 环境变量 | `deployment.config.yaml` 单一入口 + `configure.sh` + `deploy-k8s.sh` |
| **图集** | 架构 + 数据流 + K8s + 网络 + LLM Gateway | + C4 三层 + 4 条序列图 + 3 状态机 + ER + 威胁 DFD |
| **决策归档** | 散落于正文 | 附录 ADR × 12 |
| **风险归档** | 项目风险登记簿（散） | 附录 FMEA × 15 |
| **NFR** | 章节散述 | 附录 NFR 指标详表 |

---

# 附录 E：缩略语

| 缩写 | 全称 | 中文 |
|---|---|---|
| ADR | Architecture Decision Record | 架构决策记录 |
| ATT&CK | Adversarial Tactics, Techniques & Common Knowledge | MITRE 对抗知识库 |
| CVE | Common Vulnerabilities and Exposures | 通用漏洞披露 |
| CVSS | Common Vulnerability Scoring System | 通用漏洞评分 |
| DFD | Data Flow Diagram | 数据流图 |
| DLQ | Dead Letter Queue | 死信队列 |
| EPSS | Exploit Prediction Scoring System | 漏洞利用预测评分 |
| FMEA | Failure Modes and Effects Analysis | 失效模式与影响分析 |
| HPA | Horizontal Pod Autoscaler | 水平自动扩缩 |
| IoC | Indicator of Compromise | 入侵指标 |
| KEV | Known Exploited Vulnerabilities | 已知被利用漏洞 |
| LLM | Large Language Model | 大语言模型 |
| MTTR | Mean Time To Recovery | 平均恢复时间 |
| NFR | Non-Functional Requirement | 非功能需求 |
| NIST NVD | National Vulnerability Database | 国家漏洞库 |
| OIDC | OpenID Connect | 开放身份连接协议 |
| OPA | Open Policy Agent | 开放策略代理 |
| OTel | OpenTelemetry | 开放遥测 |
| OTLP | OpenTelemetry Line Protocol | OTel 传输协议 |
| PDB | Pod Disruption Budget | Pod 中断预算 |
| RBAC | Role-Based Access Control | 基于角色的访问控制 |
| RPN | Risk Priority Number | 风险优先级 |
| RPO | Recovery Point Objective | 恢复点目标 |
| RTO | Recovery Time Objective | 恢复时间目标 |
| SBOM | Software Bill of Materials | 软件物料清单 |
| SIEM | Security Information and Event Management | 安全信息与事件管理 |
| SLA | Service Level Agreement | 服务级别协议 |
| SLI | Service Level Indicator | 服务级别指标 |
| SLO | Service Level Objective | 服务级别目标 |
| SOAR | Security Orchestration, Automation and Response | 安全编排、自动化与响应 |
| SOC | Security Operations Center | 安全运营中心 |
| STRIDE | Spoofing, Tampering, Repudiation, Info disclosure, DoS, Elevation | STRIDE 威胁模型六大分类 |
| TLP | Traffic Light Protocol | 交通灯协议（情报分级） |
| TTP | Tactics, Techniques, and Procedures | 战术、技术与流程 |
| WAF | Web Application Firewall | Web 应用防火墙 |

---

> **v5.0 评审方**：安全产品经理 / 架构师 / 安全架构师 / SRE / QA / 安全测试 / DevSecOps（新增）七角色联合。
> **文档结束。**
