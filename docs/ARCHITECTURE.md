# 架构文档

## 1. 定位与边界

SIA（Security Intelligence Agent）是一个**企业内部署**的 AI 驱动安全情报聚合与分析平台。它负责：

- 从 RSS / NVD / CISA / 企业内源定时抓取安全情报
- 去重（Redis 指纹 + Milvus 语义向量）
- 调度多步 LLM 工作流做分级、打分、IoC 抽取、影响评估
- 生成日报 / 周报 / 紧急预警，通过 Web 控制台、邮件推送
- 提供 REST API 供 SOC/SIEM 集成

**不做的事**：EDR/XDR、漏扫、事件响应编排（SOAR）、端点监控。SIA 是情报层，下游告警/处置由企业现有 SOC 工具消费。

## 2. 组件拓扑

```
                    ┌──────────────────────────────┐
                    │   Users  /  SOC  /  SIEM     │
                    └──────────────┬───────────────┘
                                   │ HTTPS
                          ┌────────▼────────┐
                          │ Ingress (nginx) │
                          └───┬─────────┬───┘
                              │         │
              ┌───────────────┘         └───────────┐
              ▼ /                                    ▼ /api/
     ┌────────────────┐                     ┌─────────────────┐
     │ sia-web (SPA)  │                     │  sia-api        │
     │ nginx :8080    │ ◀──── XHR ─────▶    │  FastAPI :8080  │
     │ UID 101        │                     │  UID 1000       │
     └────────────────┘                     └────────┬────────┘
                                                     │
                                                     ▼
   ┌──────────────────────────┬───────────────────────────────┐
   │                          │                               │
   ▼                          ▼                               ▼
┌───────────┐         ┌───────────────┐              ┌────────────────┐
│  MySQL    │◀────────│  sia-consumer │              │  LLM Gateway   │
│  (TLS)    │         │  APScheduler  │─────────────▶│ (local + cloud)│
└───────────┘         │  Redis Streams│              └────────┬───────┘
                      └──────┬────────┘                       │
                             │                                │
             ┌───────────────┼───────────────┐                │
             ▼               ▼               ▼                │
       ┌────────┐      ┌──────────┐    ┌─────────┐            │
       │ Redis  │      │ Milvus   │    │ MinIO   │◀───────────┘
       │ (TLS)  │      │ vectors  │    │ reports │
       └────────┘      └──────────┘    └─────────┘
```

## 3. 组件清单

| 组件 | K8s 对象 | 技术栈 | 职责 |
|---|---|---|---|
| **sia-api** | Deployment × N | FastAPI + Uvicorn + SQLAlchemy 2 async | REST API、鉴权（JWT + API-Key + LDAP + OIDC）、RBAC、仪表板查询 |
| **sia-consumer** | Deployment × 1+ | Python + APScheduler + Redis Streams 消费者组 | 抓取调度、工作流执行、LLM 调用、落库 |
| **sia-web** | Deployment × N | React（Vite）+ nginx-unprivileged | SPA 前端 + API 反向代理 |
| **MySQL** | 外部托管 | MySQL 8.0 + aiomysql | 业务数据：情报、用户、报告元数据、审计 |
| **Redis** | 外部托管 | Redis 7 Streams + Pub/Sub | 消息队列、限流桶、会话缓存、分布式锁 |
| **Milvus** | 外部托管 | Milvus 2.4 | 情报语义向量，近似去重 |
| **MinIO** | 外部托管 | S3 兼容 | 报告 PDF / 附件归档 |

## 4. 关键数据流

### 4.1 情报采集 → 分析
```
Collector (cron)
   → 拉取源（RSS/API）
   → 去重（Redis SHA1 + Milvus kNN < 0.1）
   → xadd raw_intel_stream
Consumer (xreadgroup)
   → 加载情报 + 资产匹配
   → 执行 analyze_intel workflow
       ├─ llm_call: 分类 + 严重度
       ├─ llm_call: IoC 抽取
       ├─ python_func: 评分 & 优先级
       └─ python_func: 持久化
   → xack + P0/P1 → emergency_stream
```

### 4.2 报告生成
```
Scheduler (daily 08:00, weekly Mon 08:00)
   → xadd report_request_stream { type: daily|weekly }
Reporter consumer
   → 汇总时段内情报（按 priority、category、source）
   → LLM 生成执行摘要
   → Jinja2 → HTML → WeasyPrint → PDF
   → MinIO put_object(bucket, key)
   → xadd push_task_stream { channel: email|webhook }
```

### 4.3 鉴权链路
```
Client → Authorization: Bearer <JWT>  or  X-API-Key: <key>
       → RateLimitMiddleware (per-identity bucket)
       → Depends(get_current_user)
           ├─ JWT 验签（HS256 / RS256，key 挂载自 /etc/sia/secrets）
           ├─ API-Key 等值比较（constant-time）
           └─ DB user.status 活跃校验
       → Depends(require_role("analyst"))
       → router handler
       → 审计：audit("intel.export", actor=..., request=...)
```

## 5. 工作流引擎（analyze_intel 等）

`sia/gateway/workflow/` 里自研的**声明式多步工作流**：

- 每个工作流是一份 YAML（`workflows/*.yaml`），定义 steps + inputs/outputs 数据流
- 支持 `llm_call`（通过 LLMGateway 自动走熔断与失败回退）、`python_func`（本地 Python 函数）两种 step 类型
- 运行时 `WorkflowEngine.execute()` 按依赖图拓扑执行
- 失败重试、超时、熔断在 step 级别配置

## 6. LLM Gateway（多模型 + 脱敏）

`sia/gateway/llm/` 统一封装：

- 适配器：Anthropic、OpenAI、Google、本地 OpenAI 兼容（DeepSeek/Qwen/GLM）
- 模型元数据：`config/llm_gateway.yaml`
- **熔断器**：连续 5 次失败熔断 60s（防 API 配额耗尽）
- **失败链**：每个模型配置 fallback 顺序
- **出云脱敏**：正则 + 白名单，IP / 员工名 / 企业资产名在出云前替换为 `<REDACTED_IP_1>` 等占位符；响应后按映射表还原
- **记账**：`models/system.py::LLMCallLog` 记录 token 用量 + 成本

## 7. 存储与数据模型

核心表（`src/sia/models/`）：

- `intelligence`：情报主表（title、content、source、CVE、分类、打分、priority、状态）
- `intelligence_ioc`：关联的 IoC 指标
- `source`：订阅的情报源配置
- `report`：生成的报告元数据
- `user` / `refresh_token`：账号体系
- `system.llm_call_log` / `system.audit_log`：账本与审计

迁移由 alembic 管理；首次部署时 `migration-job` post-install hook 自动 `upgrade head`。

## 8. 安全架构摘要

详见 [`SECURITY.md`](./SECURITY.md)。关键控制：

- Secret 仅以只读文件形式挂载到 `/etc/sia/secrets/`，不写入环境变量
- 所有容器 `readOnlyRootFilesystem: true` + `drop: [ALL]`
- 应用启动时强制校验生产环境 Secret；缺失则崩溃
- RS256 JWT（推荐）；登录端点 5 req/min/IP 独立限流
- 统一审计日志（`sia.audit` logger）
- 可选 Falco 运行时检测 + OPA Gatekeeper 准入策略

## 9. 部署拓扑

单集群单命名空间，推荐至少 3 个 node 分布：

```
Namespace: sia
├─ Deployments
│   ├─ sia-api          2+ replicas  (HPA 2→8 @ 70% CPU)
│   ├─ sia-consumer     1+ replicas
│   └─ sia-web          2+ replicas
├─ Services (ClusterIP)
│   ├─ sia-api :8080
│   └─ sia-web :80
├─ Ingress
│   └─ sia-ingress    host=<INGRESS_HOST>  TLS via cert-manager
├─ ConfigMap: sia-config              (非密参数)
├─ Secret:   sia-secrets              (密钥，挂载为文件)
├─ NetworkPolicy: sia-network-policy  (限制入口/出口)
├─ PodDisruptionBudget: sia-api-pdb   (minAvailable: 1)
├─ HorizontalPodAutoscaler
└─ Jobs (post-install)
    ├─ sia-db-init-<rev>   (alembic upgrade head)
    └─ sia-db-seed-<rev>   (首次创建 admin + 默认源 + 评分策略)
```

外部依赖（托管或自建）：MySQL、Redis、Milvus、MinIO、（可选）OTLP Collector、邮件 SMTP。

## 10. 可观测性

- **日志**：JSON 结构化（`log_json_format: true`），包含 trace_id、user_id；审计事件独立 logger（`sia.audit`）
- **Metrics**：Prometheus `/metrics` 暴露，Counter/Histogram 按 FastAPI route
- **Tracing**：OpenTelemetry OTLP 出口，按 `SIA_OTLP_ENDPOINT` 配置

## 11. 不在本次范围

- **东西向 mTLS**：建议通过集群级 Istio Ambient / Linkerd 注入，Helm chart 不强制引入 sidecar
- **多集群 / 多区域灾备**：单集群设计，跨集群数据同步由平台团队方案承担
- **备份**：数据库/对象存储备份由外部托管服务或平台团队处理
