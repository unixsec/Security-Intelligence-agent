# API 参考

Base URL：`https://<INGRESS_HOST>/api/v1`
OpenAPI 实时文档：`GET /api/docs`（Swagger UI）、`GET /api/openapi.json`
ReDoc：`GET /api/redoc`

本文档聚焦**集成场景**：如何调用、鉴权、错误码、速率限制、主要资源端点。完整的请求/响应 schema 以 `/api/openapi.json` 为准。

## 1. 鉴权

SIA 支持三种鉴权，同等有效，优先级：Bearer JWT > API-Key > 匿名（仅 dev 环境）。

### 1.1 Bearer JWT（用户）

```
Authorization: Bearer eyJhbGciOi...
```

获取流程：
```bash
curl -sX POST https://<host>/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username": "alice", "password": "<pw>", "provider": "local"}'
```
返回：
```json
{
  "access_token":  "...",
  "refresh_token": "...",
  "token_type":    "bearer",
  "expires_in":    1800,
  "user": { "id": 1, "username": "alice", "role": "analyst", ... }
}
```

刷新：
```bash
curl -sX POST https://<host>/api/v1/auth/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token": "..."}'
```

JWT 默认 30 分钟有效；refresh token 7 天。算法为 **RS256**（生产推荐）或 HS256（由 `SIA_AUTH_JWT_ALGORITHM` 决定），公钥可从 `/etc/sia/secrets/SIA_AUTH_JWT_PUBLIC_KEY`（集群内）或向管理员索取。

### 1.2 API Key（机器账户）

```
X-API-Key: <key>
```

由管理员通过 `openssl rand -hex 32` 生成，写入 `deployment.config.yaml` 的 `secrets.apiKey`。**API Key 授予 admin 级权限**（设计为服务账户），因此要妥善保管、定期轮换。

### 1.3 OIDC（企业 SSO）

```bash
# 列出可用 IdP
curl https://<host>/api/v1/auth/oidc/providers

# 跳转到 IdP
curl 'https://<host>/api/v1/auth/oidc/authorize?provider=azure&redirect_uri=https://<host>/callback'

# 回调时交换 code
curl -sX POST 'https://<host>/api/v1/auth/oidc/callback?provider=azure&code=<code>&redirect_uri=https://<host>/callback'
```

## 2. 速率限制

- 默认：**30 req/min 每身份**（生产）/ 60 req/min（dev），按 JWT digest / API-Key digest / IP 分桶
- 登录相关端点：**5 req/min 每 IP**（独立桶，叠加在默认桶上）
- 超限返回 `HTTP 429 { "detail": "Rate limit exceeded. Please slow down." }`

建议客户端实现指数回退。

## 3. 错误约定

| HTTP | 场景 | 响应体 |
|---|---|---|
| 400 | 请求体语法 / 字段校验错 | `{"detail": [...pydantic错误...]}` |
| 401 | 无 / 过期 / 无效凭据 | `{"detail": "..."}` |
| 403 | 角色不足 | `{"detail": "Requires role 'analyst' or above. Your role: 'viewer'"}` |
| 404 | 资源不存在 | `{"detail": "Not found"}` |
| 423 | 账号被锁 | `{"detail": "Account is locked. Try again later."}` |
| 429 | 速率限制 | 见上 |
| 5xx | 服务端错误 | 不暴露内部堆栈 |

## 4. 主要资源

以下仅列关键端点；完整 schema 以 OpenAPI 为准。

### 4.1 健康检查

```
GET /api/v1/health        → 200 { "status": "ok", "version": "0.2.0", "env": "production" }
```
无需鉴权。用于 K8s liveness/readiness 以及 LB 监测。

### 4.2 情报（Intelligence）

```
GET  /api/v1/intelligence                      # 列表
GET  /api/v1/intelligence?priority=P0,P1
GET  /api/v1/intelligence?since=2026-04-20T00:00:00Z
GET  /api/v1/intelligence?cve=CVE-2026-12345
GET  /api/v1/intelligence?keyword=log4j        # 安全转义，匹配 title + content
GET  /api/v1/intelligence?limit=100&offset=0
GET  /api/v1/intelligence/{id}                 # 详情（含 IoC、分析、评分）
PUT  /api/v1/intelligence/{id}/review          # analyst+ 修正分类/priority
POST /api/v1/intelligence/{id}/feedback        # 处置反馈：acknowledged/false_positive/fixed
```

列表响应节选：
```json
{
  "total": 1247,
  "items": [
    {
      "id": 45678,
      "title": "...",
      "source_name": "NVD",
      "published_at": "2026-04-22T06:00:00Z",
      "cve_id": "CVE-2026-1234",
      "cvss_score": 9.8,
      "is_kev": true,
      "priority": "P0",
      "total_score": 9.2,
      "primary_category": "cve",
      "created_at": "2026-04-22T06:05:12Z"
    }
  ]
}
```

### 4.3 IoC（Indicators of Compromise）

```
GET /api/v1/intelligence/{id}/iocs             # 与情报绑定
GET /api/v1/iocs?type=ip&active=true           # 全量检索
```

IoC 类型：`ip` / `domain` / `url` / `hash_md5` / `hash_sha256` / `cve` / `email`。

### 4.4 报告

```
GET  /api/v1/reports                           # 列表
GET  /api/v1/reports/{id}                      # 元数据
GET  /api/v1/reports/{id}/html                 # 内嵌 HTML
GET  /api/v1/reports/{id}/pdf                  # 重定向至 MinIO 预签名 URL
POST /api/v1/reports/generate                  # analyst+：按条件临时生成
     body: { "type": "custom", "from": "...", "to": "...", "categories": [...] }
```

### 4.5 情报源

```
GET    /api/v1/sources                         # 列表
GET    /api/v1/sources/{id}
POST   /api/v1/sources                         # admin
PUT    /api/v1/sources/{id}                    # admin
DELETE /api/v1/sources/{id}                    # admin
POST   /api/v1/sources/{id}/test               # admin：测试抓取
```

### 4.6 仪表盘

```
GET /api/v1/dashboard/summary                  # 今日/本周计数
GET /api/v1/dashboard/priority-distribution
GET /api/v1/dashboard/category-distribution
GET /api/v1/dashboard/top-threats?limit=10
GET /api/v1/dashboard/llm-metrics              # 近 24h 调用统计
```

### 4.7 用户管理（admin）

```
GET    /api/v1/users
GET    /api/v1/users/{id}
POST   /api/v1/users
PUT    /api/v1/users/{id}
DELETE /api/v1/users/{id}
POST   /api/v1/users/{id}/reset-password
POST   /api/v1/users/{id}/unlock
```

## 5. 分页与过滤约定

- 分页：`?limit=<1-500>&offset=<≥0>`（默认 limit=50）
- 排序：`?sort=-published_at`（前缀 `-` 表示降序）
- 时间：ISO 8601，UTC，`?since=2026-04-20T00:00:00Z`
- 多值：逗号分隔，`?priority=P0,P1`

## 6. 推送渠道

SIA v0.3 已支持以下 7 种推送适配器，配置位于 `config/push_channels.yaml`，实现位于 `src/sia/adapters/push/`：

| 渠道 | 配置 key | 实现 |
|---|---|---|
| Email (SMTP/SMTPS) | `email` | `adapters/push/email.py` |
| 企业微信群机器人 | `wechat_work` | `adapters/push/wechat_work.py` |
| 微信公众号模板消息 | `wechat` | `adapters/push/wechat.py` |
| 飞书自定义机器人 | `feishu` | `adapters/push/feishu.py` |
| 钉钉自定义机器人 | `dingtalk` | `adapters/push/dingtalk.py` |
| Telegram Bot | `telegram` | `adapters/push/telegram.py` |
| 阿里云 / 腾讯云 SMS | `sms` | `adapters/push/sms.py`（阿里云已实现，腾讯云仅占位） |

调度由 `reporter/pusher/dispatcher.py` 处理：从 `push_task_stream` 消费，按 P0/P1 路由到优先渠道，支持指数退避重试与死信队列。

通用 Webhook（HTTP POST + HMAC 签名）目前不在 v0.3 范围，计划在 v0.4 加入。

## 7. 集成示例

### 7.1 Python（服务账户）

```python
import httpx

SIA_URL = "https://<host>"
API_KEY = "..."

client = httpx.Client(
    base_url=f"{SIA_URL}/api/v1",
    headers={"X-API-Key": API_KEY},
    timeout=30,
)

# 最近 1 小时 P0 情报
import datetime as dt
since = (dt.datetime.utcnow() - dt.timedelta(hours=1)).isoformat() + "Z"
r = client.get("/intelligence", params={"priority": "P0", "since": since})
r.raise_for_status()
for item in r.json()["items"]:
    print(item["cve_id"], item["title"])
```

### 7.2 SIEM 轮询（伪代码）

```
while True:
    last_seen = load_checkpoint()
    resp = GET /api/v1/intelligence?since=last_seen&priority=P0,P1&limit=500
    for item in resp.items:
        push_to_siem(item)
    save_checkpoint(max(item.created_at for item in resp.items))
    sleep(60)
```

### 7.3 cURL 快速验证

```bash
API_KEY='...'
curl -sH "X-API-Key: $API_KEY" https://<host>/api/v1/health | jq
curl -sH "X-API-Key: $API_KEY" 'https://<host>/api/v1/intelligence?priority=P0&limit=5' | jq .total
```

## 8. 安全合约

- **幂等**：PUT/DELETE 幂等；POST 创建幂等需客户端自带 UUID（可选 header `X-Request-Id`）
- **不返回敏感字段**：user 响应绝不含 `hashed_password`、`api_key`；intelligence 响应按需脱敏内部 IP
- **审计**：所有**写**端点在服务端自动调 `audit()`；集成方不需要额外调用

## 9. 版本演进

- API 版本前缀 `/api/v1/`；破坏性变更会升级到 `/api/v2/`，`/v1` 至少维持 1 个大版本
- 字段新增为非破坏；字段删除或语义变更会在 `/api/v1/_meta/deprecations` 提前标注（规划中）

---

*SIA v0.2.0 | REST API Reference*
