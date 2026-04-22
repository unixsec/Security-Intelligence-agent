# 用户手册

面向 SIA Web 控制台的最终使用者——安全分析师、SOC 值班、管理员。

> 管理员请额外参考：[`OPERATIONS_GUIDE.md`](./OPERATIONS_GUIDE.md)。

## 1. 登录

1. 打开公司下发的 SIA 地址（形如 `https://sia.company.com`）
2. 使用企业账号（LDAP / OIDC）或本地账号登录
3. 首次使用建议立即修改密码（本地账号）

账户被锁定时会显示 `Account is locked. Try again later.` —— 由系统策略决定（默认 5 次失败后锁 30 分钟），联系管理员可立即解锁。

## 2. 角色与权限

| 角色 | 能做什么 |
|---|---|
| **viewer** | 浏览情报、查看报告、下载导出 |
| **analyst** | viewer + 新增/修改情报评分、标注 IoC、触发临时分析 |
| **admin** | analyst + 管理用户、配置情报源、调整评分策略、查看审计日志 |

登录后右上角显示当前角色。如角色不足访问某功能会收到 `403`。

## 3. 主要功能

### 3.1 仪表盘（Dashboard）

- 今日 / 本周新增情报数量
- 按 priority（P0/P1/P2/P3）分布
- 按 category（CVE、APT、恶意软件、钓鱼、泄露、供应链 …）分布
- 最近 LLM 调用成功率、平均延迟
- P0 紧急告警卡片（近 24 小时未处置）

### 3.2 情报列表（Intelligence）

- 按 priority / source / 时间范围 / CVE 编号 / 关键词检索
- 关键词搜索对 `title` 和 `content` 使用安全转义的 `ILIKE %keyword%`，无 SQL 注入风险
- 每条情报卡片显示：标题、来源、发布时间、priority、评分、分类、CVE ID、CVSS、是否在 KEV 列表

点击情报可看：
- 结构化正文（HTML 已去净）
- LLM 分析摘要（影响、TTP、受影响资产、缓解建议）
- 抽取的 IoC（IP / 域名 / 哈希 / CVE）
- 评分明细（relevance / severity / timeliness / actionability / quality）+ 综合分与 priority

**analyst 可做**：
- 修正分类、priority
- 补充 / 删除 IoC
- 标注 "已处置" / "误报"（反馈回流到 `feedback_stream` 用于后续评分校正）

### 3.3 报告（Reports）

- 每日报告（08:00 自动生成覆盖前一日）
- 每周报告（周一 08:00 自动生成覆盖上周）
- 临时报告：选时间段 + 分类过滤，触发生成（需 analyst 权限）
- 报告格式：HTML 网页预览 + PDF 导出（MinIO 归档）
- 订阅：点 "订阅" 按钮即接收邮件推送（需管理员先配置 SMTP）

### 3.4 情报源（Sources，仅 admin）

- RSS / HTTP JSON / 自定义插件三类
- 配置字段：URL、抓取间隔、认证（若需）、默认分类、抓取模板
- 启用 / 停用 / 测试抓取

### 3.5 用户管理（Users，仅 admin）

- 新建 / 冻结 / 删除本地账号
- 重置密码
- 修改角色
- LDAP / OIDC 用户自动创建（首次登录时），可在此调整默认角色

### 3.6 审计（Audit，仅 admin）

- 登录历史（成功 / 失败 / 锁定）
- 管理员敏感操作（用户变更、源配置、报告导出）
- 可按 actor / event / 时间 / IP 过滤导出 CSV

## 4. 常见任务

### 4.1 把新发现的 CVE 加入关注列表

1. 在搜索栏输入 CVE ID（如 `CVE-2026-12345`）
2. 若已被系统抓到，直接打开查看；否则管理员可在"情报源"里添加 NVD 的该 CVE 订阅
3. analyst 标注 priority 或 "需关注"

### 4.2 导出一周 P0/P1 情报

1. 进入 "情报列表"
2. 过滤 priority = P0 / P1
3. 时间范围选 "最近 7 天"
4. 点击"导出" → CSV / JSON

### 4.3 配置邮件推送

1. 管理员在 "系统设置 → 通知渠道" 添加 SMTP
2. 订阅：个人 → "订阅设置" → 勾选需要接收的事件（每日报告 / P0 紧急 / 特定 category）

## 5. API 集成

见 [`API_REFERENCE.md`](./API_REFERENCE.md)。常见场景：

- SOC SIEM 拉取 P0/P1 情报：轮询 `GET /api/v1/intelligence?priority=P0,P1&since=<ts>`
- 自动创建 SOAR 工单：监听 `GET /api/v1/intelligence?status=new` + webhook（未来规划）

API 鉴权：
- 机器账户用 `X-API-Key: <token>`（管理员签发）
- 人机交互继续用 Bearer JWT

## 6. 常见问题

| 问题 | 解答 |
|---|---|
| 登录后立刻跳回登录页 | Access token 默认 30 分钟过期；浏览器时间严重偏差也会验证失败 |
| 看不到"情报源"菜单 | 需要 admin 角色，联系管理员 |
| 搜索关键词无结果 | 检查拼写；SIA 默认只索引最近 30 天情报，可调范围 |
| PDF 导出失败 | 后端 WeasyPrint 依赖库未就位；联系运维查 sia-api 日志 |
| 429 Too Many Requests | 触发限流；默认 30 req/min/身份、5 req/min/IP（登录）；等 1 分钟 |
| 账号被锁 | 连续 5 次密码错误触发；30 分钟后自动解锁，或联系管理员手动解锁 |

## 7. 安全使用建议

- 不要把 API Key 写进个人代码或聊天记录
- 浏览器不要保存密码；使用公司统一 SSO 优先
- 导出的 CSV/PDF 按企业数据分类分级标识妥善保管
- 发现可疑情报（可能含 Prompt Injection / 恶意链接）用 "举报" 功能通知管理员，不要直接点击正文链接

---

*SIA v0.2.0 | User Manual*
