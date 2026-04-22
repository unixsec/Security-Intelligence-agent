# 安全洞察与情报分析智能体 — 系统设计方案 v1.0

> **文档版本：** 1.0
> **日期：** 2026-03-28
> **作者：** alex &lt;unix_sec@163.com&gt;
> **状态：** 最终稿
> **密级：** 内部机密

---

## 目录

- [第一部分：战略概述](#第一部分战略概述)
  - [1. 执行摘要](#1-执行摘要)
  - [2. 项目背景与目标](#2-项目背景与目标)
  - [3. 核心设计原则](#3-核心设计原则)
- [第二部分：系统架构](#第二部分系统架构)
  - [4. 总体架构](#4-总体架构)
  - [5. 技术选型](#5-技术选型)
  - [6. 部署架构](#6-部署架构)
- [第三部分：详细设计](#第三部分详细设计)
  - [7. 情报源管理子系统](#7-情报源管理子系统)
  - [8. 情报采集引擎](#8-情报采集引擎)
  - [9. AI 分析管线](#9-ai-分析管线)
  - [10. 去重与事件追踪引擎](#10-去重与事件追踪引擎)
  - [11. 情报评分与分级模型](#11-情报评分与分级模型)
  - [12. 知识图谱与实体关联](#12-知识图谱与实体关联)
  - [13. MITRE ATT&CK 映射](#13-mitre-attck-映射)
  - [14. 报告生成子系统](#14-报告生成子系统)
  - [15. 紧急情报响应机制](#15-紧急情报响应机制)
  - [16. 通知与分发子系统](#16-通知与分发子系统)
  - [17. Web 控制台与查询系统](#17-web-控制台与查询系统)
  - [18. 反馈闭环与持续优化](#18-反馈闭环与持续优化)
- [第四部分：数据架构](#第四部分数据架构)
  - [19. 数据模型设计](#19-数据模型设计)
  - [20. 向量数据库设计](#20-向量数据库设计)
  - [21. 数据生命周期管理](#21-数据生命周期管理)
- [第五部分：安全与合规](#第五部分安全与合规)
  - [22. 系统自身安全设计](#22-系统自身安全设计)
  - [23. 数据合规](#23-数据合规)
  - [24. 威胁建模（系统自身）](#24-威胁建模系统自身)
- [第六部分：运维与保障](#第六部分运维与保障)
  - [25. 监控与可观测性](#25-监控与可观测性)
  - [26. 容错与灾备](#26-容错与灾备)
  - [27. 性能与容量规划](#27-性能与容量规划)
- [第七部分：实施规划](#第七部分实施规划)
  - [28. 分阶段上线计划](#28-分阶段上线计划)
  - [29. 测试策略](#29-测试策略)
  - [30. 成本估算](#30-成本估算)
  - [31. 项目风险登记簿](#31-项目风险登记簿)
- [附录](#附录)

---

# 第一部分：战略概述

## 1. 执行摘要

本方案为某大型上市跨国智能网联汽车企业设计一套 **安全洞察与情报分析智能体（Security Intelligence Agent, SIA）**。该系统通过自动化采集全球安全情报、利用私有化大语言模型（LLM）进行深度分析和价值判断，向企业高管和安全运营团队定时推送结构化安全简报，并在重大安全事件发生时即时告警。

**核心价值主张：**

| 维度 | 当前痛点 | SIA 解决方案 |
|------|---------|-------------|
| **情报覆盖** | 依赖人工浏览，覆盖面有限 | 自动化采集 200+ 情报源，7×24 全球覆盖 |
| **响应速度** | 重大事件感知滞后 | P0 事件分钟级即时推送 |
| **分析深度** | 原始信息堆砌，缺乏关联分析 | LLM 驱动的多维分析、ATT&CK 映射、知识图谱关联 |
| **决策支撑** | 高管无法快速获取安全态势 | 分层报告体系（高管简版 + 运营详版） |
| **合规感知** | 法规变化靠人工跟踪 | 自动监控全球法规变化，影响评估即时推送 |
| **历史积累** | 安全知识分散在个人脑中 | 结构化知识库 + 知识图谱，组织智慧可持续沉淀 |

---

## 2. 项目背景与目标

### 2.1 企业画像

- **企业性质：** 已上市大型跨国企业
- **主营业务：** 智能网联汽车的制造和销售
- **主要市场：** 欧盟、中国大陆、东南亚
- **员工规模：** 万人以上
- **安全团队规模：** CISO 领导下的安全运营团队（SOC）、安全架构团队、合规团队

### 2.2 安全关注领域（按优先级排序）

**Tier 1 — 企业通用 IT 安全：**
- 办公网络基础设施（AD 域控、DNS、DHCP）
- 企业应用系统（ERP/PLM/CRM/MES/OA）
- 邮件系统（Exchange/O365）
- 云平台（私有云 + 混合云）
- 数据库系统
- 终端安全（PC、移动设备）
- VPN 及远程访问
- Web 应用安全

**Tier 2 — 汽车行业特定技术领域安全：**
- 车联网（V2X、T-Box、TSP 平台）
- 自动驾驶（传感器、算法、高精地图）
- OTA 空中升级
- 智能座舱
- 智能充电（充电桩、充电网络）
- 工控系统（SCADA/PLC/DCS/MES）

**Tier 3 — 供应链与合作伙伴安全：**
- 芯片供应商安全态势
- Tier 1/Tier 2 零部件供应商
- 软件供应链（开源组件、第三方 SDK）
- 云服务供应商

### 2.3 项目目标

| 目标编号 | 目标描述 | 可衡量指标 |
|---------|---------|-----------|
| G1 | 实现全球安全情报自动化采集与分析 | 每日处理 500+ 条原始情报 |
| G2 | 按时推送多层级安全简报 | 日报准时率 ≥ 99%，年缺失 ≤ 3 期 |
| G3 | 重大安全事件即时感知与告警 | P0 事件从发生到推送 ≤ 15 分钟 |
| G4 | 降低安全团队情报分析人力投入 | 节省 ≥ 60% 人工情报分析时间 |
| G5 | 建立可持续增长的安全知识库 | 年度知识库增量 ≥ 10 万条结构化情报 |
| G6 | 全球安全法规变化即时感知 | 法规变化从发布到推送 ≤ 24 小时 |
| G7 | 全部组件私有化部署 | 零公有云依赖，数据不出企业边界 |

---

## 3. 核心设计原则

| 编号 | 原则 | 说明 |
|-----|------|------|
| P1 | **全私有化部署** | 所有组件运行在企业 K8s 集群，数据不出企业边界 |
| P2 | **低代码优先** | 优先使用 Dify 可视化编排，减少自定义代码维护成本 |
| P3 | **模型可替换** | LLM 通过统一适配层调用，可随时切换 DeepSeek/Qwen/GLM/Kimi 等 |
| P4 | **渐进式增强** | 分阶段上线，核心功能先行，高级功能逐步迭代 |
| P5 | **优雅降级** | 任何单一组件故障不应导致整体系统不可用 |
| P6 | **安全第一** | 系统自身的安全性不低于其所保护的资产 |
| P7 | **数据驱动优化** | 通过反馈闭环持续提升情报质量和分析准确度 |
| P8 | **可审计** | 所有关键操作留痕，满足内部审计要求 |

---

# 第二部分：系统架构

## 4. 总体架构

### 4.1 系统架构全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        安全洞察与情报分析智能体 (SIA)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     表现层 (Presentation Layer)                      │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │    │
│  │  │ Web 控制台│ │企业微信Bot│ │ 飞书 Bot │ │ 邮件网关 │ │ 短信网关 │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     业务服务层 (Service Layer)                       │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ 报告生成服务  │ │ 紧急响应服务  │ │ 通知分发服务  │                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ 情报源管理    │ │ 反馈收集服务  │ │ 用户权限服务  │                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     智能分析层 (Intelligence Layer)                   │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ LLM 分析引擎  │ │ 评分分级引擎  │ │ 去重追踪引擎  │                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ 知识图谱引擎  │ │ATT&CK 映射   │ │ 趋势分析引擎  │                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  │  ┌──────────────┐ ┌──────────────┐                                 │    │
│  │  │ 法规变化分析  │ │ 供应链风险    │                                 │    │
│  │  └──────────────┘ └──────────────┘                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │               数据采集与处理层 (Collection Layer)                     │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ RSS 采集器    │ │ 网页爬虫引擎  │ │ API 采集器    │                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │    │
│  │  │ 微信公众号    │ │ 暗网监控      │ │ 漏洞库同步    │                │    │
│  │  │ (WeRSS)      │ │ (Tor 代理)    │ │ (NVD/CNVD)   │                │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘                │    │
│  │  ┌──────────────┐ ┌──────────────┐                                 │    │
│  │  │ 社交媒体监控  │ │ 品牌仿冒监控  │                                 │    │
│  │  └──────────────┘ └──────────────┘                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     数据存储层 (Storage Layer)                       │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │    │
│  │  │ MySQL        │ │ Milvus       │ │ Redis        │ │ MinIO      │ │    │
│  │  │ (结构化数据)  │ │ (向量数据库)  │ │ (缓存/队列)  │ │ (文件存储)  │ │    │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │    │
│  │  ┌──────────────┐ ┌──────────────┐                                 │    │
│  │  │ Neo4j        │ │ Elasticsearch│                                 │    │
│  │  │ (知识图谱)    │ │ (全文检索)    │                                 │    │
│  │  └──────────────┘ └──────────────┘                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     基础设施层 (Infrastructure)                      │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐          │    │
│  │  │ K8s 集群   │ │ Dify 平台  │ │ 私有 LLM   │ │ 监控告警   │          │    │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 核心数据流

```
                        ┌─────────────────────────────────┐
                        │          情报源（外部）            │
                        │  RSS │ 网站 │ 公众号 │ API │ 暗网  │
                        └───────────────┬─────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │    ① 情报采集层                 │
                        │  多协议采集器 + 频率控制器        │
                        └───────────────┬───────────────┘
                                        │ 原始情报
                                        ▼
                        ┌───────────────────────────────┐
                        │    ② 预处理层                   │
                        │  清洗 → 去噪 → 语言检测 → 翻译   │
                        │  → 结构化提取 → 向量化            │
                        └───────────────┬───────────────┘
                                        │ 标准化情报
                                        ▼
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│   ③ P0/P1 检测       │  │   ④ 语义去重         │  │   ⑤ 入库存储         │
│  关键词 + 规则匹配    │  │  向量相似度比对       │  │  MySQL + Milvus     │
│  → 紧急通道           │  │  事件聚合             │  │  + Elasticsearch    │
└─────────┬───────────┘  └─────────┬───────────┘  └─────────────────────┘
          │ 紧急情报                │ 去重后情报
          ▼                         ▼
┌─────────────────────┐  ┌─────────────────────┐
│  ⑥ 紧急分析 + 推送   │  │   ⑦ LLM 深度分析     │
│  即时推送通道         │  │  分类 → 评分 → 点评   │
│  CISO/CTO 直达       │  │  → ATT&CK 映射       │
└─────────────────────┘  │  → 知识图谱关联       │
                         │  → 影响面分析          │
                         └─────────┬───────────┘
                                   │ 分析后情报
                                   ▼
                         ┌─────────────────────┐
                         │   ⑧ 报告生成引擎     │
                         │  模板渲染 + LLM 撰写  │
                         │  高管版 + 运营版      │
                         └─────────┬───────────┘
                                   │ 成品报告
                                   ▼
                         ┌─────────────────────┐
                         │   ⑨ 多渠道分发        │
                         │  企微 │ 飞书 │ 邮件   │
                         └─────────┬───────────┘
                                   │
                                   ▼
                         ┌─────────────────────┐
                         │   ⑩ 反馈收集         │
                         │  评价 → 统计 → 调优   │
                         └─────────────────────┘
```

### 4.3 Dify Workflow 编排总览

系统核心流程通过 Dify 平台进行可视化编排，减少自定义代码。以下为 Dify 中需要创建的 Workflow 清单：

| Workflow ID | 名称 | 触发方式 | 职责 |
|-------------|------|---------|------|
| WF-COLLECT-RSS | RSS 情报采集 | CronJob 0 */4 * * * | 定时拉取 RSS 源 |
| WF-COLLECT-WEB | 网页情报抓取 | CronJob 0 1,13 * * * | 抓取目标网站内容 |
| WF-COLLECT-API | API 情报采集 | CronJob 0 */6 * * * | 调用 NVD/CNVD 等 API |
| WF-PREPROCESS | 情报预处理 | 事件触发（新情报入库） | 清洗、翻译、结构化、向量化 |
| WF-DEDUP | 语义去重 | 事件触发（预处理完成） | 向量比对去重、事件聚合 |
| WF-EMERGENCY | 紧急情报检测 | 事件触发（新情报入库） | P0/P1 关键词匹配与规则检测 |
| WF-EMERGENCY-PUSH | 紧急情报推送 | 事件触发（P0/P1 检出） | 即时分析 + 推送 |
| WF-ANALYZE | LLM 深度分析 | CronJob 0 4 * * * | 批量情报分析、评分、分类 |
| WF-REPORT-DAILY | 日报生成 | CronJob 0 6 * * 1-5 | 生成日报 |
| WF-REPORT-WEEKLY | 周报生成 | CronJob 0 12 * * 5 | 生成周报 |
| WF-REPORT-MONTHLY | 月报生成 | 调度服务触发 | 生成月报 |
| WF-REPORT-SEMI | 半年报生成 | 调度服务触发 | 生成半年报 |
| WF-REPORT-ANNUAL | 年报生成 | 调度服务触发 | 生成年报 |
| WF-PUSH | 报告推送 | 事件触发（报告生成完成） | 多渠道分发 |
| WF-HEALTH | 情报源健康巡检 | CronJob 0 5 * * * | 检查所有情报源可用性 |
| WF-FEEDBACK | 反馈处理 | 事件触发（收到反馈） | 反馈统计与模型调优 |
| WF-SOURCE-MANAGE | 情报源管理 | API 调用 | 情报源增删改查 |
| WF-REGULATION | 法规变化检测 | CronJob 0 2 * * * | 监控全球法规变化 |

---

## 5. 技术选型

### 5.1 技术栈全景

| 层级 | 组件 | 技术选型 | 选型理由 | 私有化部署 |
|------|------|---------|---------|-----------|
| **LLM** | 默认模型 | DeepSeek-V3 / DeepSeek-R1 | 中文能力强，开源可私有部署 | ✅ |
| | 备选模型 | Qwen2.5/GLM-4/Kimi | 通过统一接口适配 | ✅ |
| | 嵌入模型 | bge-large-zh-v1.5 | 中文向量化效果优异，BAAI 开源 | ✅ |
| **编排** | Workflow | Dify | 低代码编排，企业已部署 | ✅ |
| **采集** | RSS | Feedparser (Python) | 轻量级 RSS 解析 | ✅ |
| | 网页抓取 | Crawl4AI / Playwright | 动态渲染 + 结构化提取 | ✅ |
| | 微信公众号 | WeRSS | 公众号转 RSS | ✅ |
| **存储** | 关系型数据库 | MySQL 8.0 | 企业已有，结构化数据存储 | ✅ |
| | 向量数据库 | Milvus 2.x | 开源，K8s 原生，高性能向量检索 | ✅ |
| | 缓存/消息队列 | Redis 7.x + Redis Streams | 轻量级缓存与消息队列 | ✅ |
| | 全文检索 | Elasticsearch 8.x | 历史情报全文检索 | ✅ |
| | 知识图谱 | Neo4j Community | 实体关系图谱存储与查询 | ✅ |
| | 文件存储 | MinIO | S3 兼容对象存储，报告文件存储 | ✅ |
| **后端** | API 服务 | Python FastAPI | 轻量高性能，团队熟悉 Python | ✅ |
| | 任务调度 | APScheduler + K8s CronJob | 灵活调度 + 容器化 | ✅ |
| **前端** | Web 控制台 | Vue 3 + Element Plus | 低学习成本，生态完善 | ✅ |
| **监控** | 指标采集 | Prometheus + Grafana | K8s 生态标准选型 | ✅ |
| | 日志 | Loki + Promtail | 轻量级日志方案 | ✅ |
| | 告警 | Alertmanager | 与 Prometheus 集成 | ✅ |
| **安全** | 凭证管理 | K8s Secrets + Vault (可选) | 企业要求 | ✅ |
| | 网络策略 | K8s NetworkPolicy + Ingress | 网络隔离 | ✅ |

### 5.2 LLM 统一适配层设计

为实现模型可替换，设计统一的 LLM 调用适配层：

```
┌─────────────────────────────────────────────┐
│             LLM Gateway (统一网关)            │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │           统一调用接口                   │ │
│  │  - chat_completion(messages, params)   │ │
│  │  - embedding(text)                    │ │
│  │  - structured_output(schema, prompt)  │ │
│  └────────────────────────────────────────┘ │
│                    │                         │
│  ┌────────┬────────┼────────┬────────┐      │
│  │        │        │        │        │      │
│  ▼        ▼        ▼        ▼        ▼      │
│ DeepSeek  Qwen    GLM     Kimi    Claude    │
│ Adapter  Adapter Adapter Adapter  Adapter   │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │  功能模块                               │ │
│  │  - 负载均衡（多模型实例）                 │ │
│  │  - 故障转移（主→备模型自动切换）           │ │
│  │  - 速率限制（QPS / TPM 配额）            │ │
│  │  - 请求日志与计量                        │ │
│  │  - 超时控制 + 指数退避重试               │ │
│  │  - Prompt 模板管理                      │ │
│  │  - 响应缓存（相同输入短期内复用）          │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

**配置示例（YAML）：**

```yaml
llm_gateway:
  default_model: deepseek-v3
  models:
    deepseek-v3:
      endpoint: http://llm-deepseek.internal:8080/v1
      api_key_secret: k8s-secret://sia-secrets/deepseek-api-key
      max_tokens: 8192
      temperature: 0.3
      timeout_seconds: 120
      max_retries: 3
      rate_limit:
        requests_per_minute: 60
        tokens_per_minute: 100000
    qwen2.5:
      endpoint: http://llm-qwen.internal:8080/v1
      api_key_secret: k8s-secret://sia-secrets/qwen-api-key
      max_tokens: 8192
      temperature: 0.3
      timeout_seconds: 120
      max_retries: 3
      rate_limit:
        requests_per_minute: 40
        tokens_per_minute: 80000

  failover:
    enabled: true
    primary: deepseek-v3
    secondary: qwen2.5
    trigger_conditions:
      - consecutive_failures: 3
      - error_rate_percent: 50
      - latency_p99_ms: 30000

  embedding:
    model: bge-large-zh-v1.5
    endpoint: http://embedding-service.internal:8080/v1
    dimension: 1024
    batch_size: 32
```

---

## 6. 部署架构

### 6.1 K8s 集群部署拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                    K8s Cluster (企业私有云)                       │
│                                                                 │
│  Namespace: sia-system                                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Deployments                                               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │  │
│  │  │ sia-api     │ │ sia-web     │ │ sia-gateway  │         │  │
│  │  │ replicas: 2 │ │ replicas: 2 │ │ replicas: 2  │         │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘         │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │  │
│  │  │ sia-collect  │ │sia-analyze  │ │ sia-report   │         │  │
│  │  │ replicas: 2 │ │ replicas: 2 │ │ replicas: 1  │         │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘         │  │
│  │  ┌─────────────┐ ┌─────────────┐                          │  │
│  │  │sia-emergency│ │ sia-push    │                          │  │
│  │  │ replicas: 2 │ │ replicas: 1 │                          │  │
│  │  └─────────────┘ └─────────────┘                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Namespace: sia-data                                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ StatefulSets                                              │  │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ │  │
│  │  │ MySQL     │ │ Milvus    │ │ Redis     │ │ Neo4j     │ │  │
│  │  │ Primary+  │ │ Standalone│ │ Sentinel  │ │ Community │ │  │
│  │  │ Replica   │ │ /Cluster  │ │ 3-node    │ │           │ │  │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ │  │
│  │  ┌───────────┐ ┌───────────┐                              │  │
│  │  │ ES        │ │ MinIO     │                              │  │
│  │  │ 3-node    │ │ 4-node    │                              │  │
│  │  └───────────┘ └───────────┘                              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Namespace: sia-monitor                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐             │  │
│  │  │ Prometheus │ │ Grafana    │ │ Loki       │             │  │
│  │  └────────────┘ └────────────┘ └────────────┘             │  │
│  │  ┌────────────┐                                           │  │
│  │  │Alertmanager│                                           │  │
│  │  └────────────┘                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Namespace: dify                                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Dify 平台（已有部署）                                      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Namespace: llm-serving                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  私有化 LLM 服务（已有部署）                                 │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 网络架构

```
                    企业防火墙
                        │
              ┌─────────┴─────────┐
              │    Ingress        │
              │  (Nginx/Traefik)  │
              └─────────┬─────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
    ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
    │ sia-web   │ │ sia-api   │ │ dify      │
    │ (前端)    │ │ (后端)    │ │ (编排)    │
    └───────────┘ └─────┬─────┘ └───────────┘
                        │
                  K8s Service Mesh
                  (内部服务通信)
                        │
          ┌─────────────┼─────────────┐
          │             │             │
    ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
    │ 数据层     │ │ LLM 层   │ │ 外部采集   │
    │ (sia-data) │ │(llm-srv) │ │ (egress)  │
    └───────────┘ └───────────┘ └─────┬─────┘
                                      │
                              企业出口代理
                              (Squid/正向代理)
                                      │
                                  互联网
```

**网络策略要点：**
- 外部采集流量必须经企业出口代理，支持审计和域名白名单
- 数据层 Namespace 仅允许来自 sia-system 的入站连接
- LLM 层仅允许来自 sia-system 和 dify 的入站连接
- 所有跨 Namespace 通信使用 K8s NetworkPolicy 控制

### 6.3 存储架构

| 数据类型 | 存储介质 | 存储类 | 容量估算（年） |
|---------|---------|-------|-------------|
| 结构化情报数据 | MySQL | SSD PV | ~50 GB |
| 向量索引 | Milvus | SSD PV | ~20 GB |
| 全文索引 | Elasticsearch | SSD PV | ~100 GB |
| 知识图谱 | Neo4j | SSD PV | ~10 GB |
| 报告文件 | MinIO | HDD PV | ~50 GB |
| 缓存/队列 | Redis | Memory | 4 GB |
| 日志 | Loki | HDD PV | ~200 GB |

---

# 第三部分：详细设计

## 7. 情报源管理子系统

### 7.1 情报源分类体系

```
情报源
├── 按协议分类
│   ├── RSS / Atom 订阅
│   ├── 网页抓取 (HTTP/HTTPS)
│   ├── API 接口 (REST/GraphQL)
│   ├── 微信公众号 (via WeRSS)
│   └── 暗网 (.onion via Tor 代理)
│
├── 按内容分类
│   ├── 漏洞数据库 (NVD, CNVD, CNNVD, ExploitDB)
│   ├── 安全资讯媒体 (The Hacker News, BleepingComputer, FreeBuf, 安全客)
│   ├── 厂商安全公告 (Microsoft, Apple, Google, 华为, 高通等)
│   ├── 政府/监管机构 (CISA, ENISA, 工信部, 网信办, PDPA 各国)
│   ├── 安全研究团队 (Google Project Zero, 腾讯玄武, 奇安信)
│   ├── 行业组织 (Auto-ISAC, FIRST, OWASP)
│   ├── 社交媒体 (Twitter/X 安全研究员, GitHub Advisory)
│   ├── 法规数据库 (EUR-Lex, 中国法规网, ASEAN 法律数据库)
│   └── 暗网论坛 (监控企业名称/数据泄露)
│
└── 按地域分类
    ├── 全球 (NVD, MITRE, FIRST)
    ├── 欧盟 (ENISA, CERT-EU, EUR-Lex)
    ├── 中国 (CNVD, CNNVD, FreeBuf, 安全客, 工信部, 网信办)
    ├── 美国 (CISA, US-CERT, NIST)
    ├── 东南亚 (各国 CERT, PDPA 监管机构)
    └── 其他 (JPCERT, KISA, AusCERT 等)
```

### 7.2 情报源数据模型

```sql
-- 情报源主表
CREATE TABLE intel_sources (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(200) NOT NULL COMMENT '情报源名称',
    slug            VARCHAR(100) UNIQUE NOT NULL COMMENT '唯一标识符',
    source_type     ENUM('rss', 'web_scrape', 'api', 'wechat', 'darkweb', 'manual') NOT NULL,
    content_type    ENUM('vuln_db', 'news_media', 'vendor_advisory', 'gov_regulator',
                         'research_team', 'industry_org', 'social_media', 'regulation_db',
                         'darkweb_forum', 'other') NOT NULL,
    region          ENUM('global', 'eu', 'cn', 'us', 'sea', 'jp', 'kr', 'other') NOT NULL,
    language        ENUM('zh', 'en', 'multi') DEFAULT 'en',
    url             VARCHAR(2000) NOT NULL COMMENT '采集地址',

    -- 采集配置
    fetch_interval  INT DEFAULT 240 COMMENT '采集间隔（分钟）',
    fetch_method    JSON COMMENT '采集方法配置（选择器、分页规则等）',
    auth_config     VARCHAR(200) COMMENT 'K8s Secret 引用路径',
    proxy_required  BOOLEAN DEFAULT FALSE COMMENT '是否需要代理',
    tor_required    BOOLEAN DEFAULT FALSE COMMENT '是否需要 Tor',

    -- 评估指标
    reliability     TINYINT DEFAULT 3 COMMENT '可靠性评级 1-5',
    authority       TINYINT DEFAULT 3 COMMENT '权威性评级 1-5',
    timeliness      TINYINT DEFAULT 3 COMMENT '时效性评级 1-5',

    -- 状态管理
    status          ENUM('active', 'paused', 'error', 'deprecated') DEFAULT 'active',
    error_count     INT DEFAULT 0 COMMENT '连续失败次数',
    last_fetch_at   DATETIME COMMENT '最近采集时间',
    last_success_at DATETIME COMMENT '最近成功时间',
    last_error_msg  TEXT COMMENT '最近错误信息',

    -- 配额控制
    daily_quota     INT DEFAULT 100 COMMENT '每日最大采集次数',
    daily_used      INT DEFAULT 0 COMMENT '当日已使用次数',

    -- 审计
    created_by      VARCHAR(100) NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by      VARCHAR(100),
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_source_type (source_type),
    INDEX idx_content_type (content_type),
    INDEX idx_region (region)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 搜索关键词表
CREATE TABLE search_keywords (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    keyword         VARCHAR(200) NOT NULL COMMENT '关键词',
    keyword_en      VARCHAR(200) COMMENT '英文关键词（用于英文源搜索）',
    category        ENUM('general_it', 'automotive', 'regulation', 'supply_chain',
                         'brand_protection', 'custom') NOT NULL,
    sub_category    VARCHAR(100) COMMENT '子分类',
    priority        TINYINT DEFAULT 3 COMMENT '优先级 1-5',
    is_negative     BOOLEAN DEFAULT FALSE COMMENT '是否为排除词',
    status          ENUM('active', 'paused', 'deprecated') DEFAULT 'active',
    search_engines  JSON COMMENT '适用的搜索引擎列表',
    daily_quota     INT DEFAULT 10 COMMENT '每日搜索次数上限',
    daily_used      INT DEFAULT 0 COMMENT '当日已使用次数',
    created_by      VARCHAR(100) NOT NULL,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by      VARCHAR(100),
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 情报源变更审计日志
CREATE TABLE source_audit_log (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    entity_type     ENUM('source', 'keyword') NOT NULL,
    entity_id       BIGINT NOT NULL,
    action          ENUM('create', 'update', 'delete', 'status_change') NOT NULL,
    old_value       JSON,
    new_value       JSON,
    operator        VARCHAR(100) NOT NULL,
    operated_at     DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_operated_at (operated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 7.3 情报源健康监控机制

```
┌─────────────────────────────────────────────┐
│           情报源健康巡检 Workflow              │
│           (WF-HEALTH, 每日 05:00)            │
├─────────────────────────────────────────────┤
│                                             │
│  for each source in active_sources:         │
│    │                                        │
│    ├─ 1. 发送探测请求                        │
│    │     HTTP HEAD / RSS fetch / API ping    │
│    │                                        │
│    ├─ 2. 判断结果                            │
│    │     ├─ 成功 → error_count = 0           │
│    │     │         status = active           │
│    │     │         更新 last_success_at       │
│    │     │                                   │
│    │     └─ 失败 → error_count += 1          │
│    │               │                         │
│    │               ├─ error_count < 3        │
│    │               │   → 记录警告日志          │
│    │               │                         │
│    │               ├─ error_count == 3       │
│    │               │   → status = error      │
│    │               │   → 发送告警通知          │
│    │               │   → 通知安全运营团队      │
│    │               │                         │
│    │               └─ error_count >= 7       │
│    │                   → 考虑自动暂停          │
│    │                   → 升级告警级别          │
│    │                                        │
│    └─ 3. 记录健康指标到 Prometheus            │
│                                             │
│  生成健康巡检摘要报告                          │
│  → 发送给安全运营团队                          │
└─────────────────────────────────────────────┘
```

**监控指标（Prometheus）：**

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `sia_source_fetch_total` | Counter | 采集总次数（按 source, status 标签） |
| `sia_source_fetch_duration_seconds` | Histogram | 采集耗时分布 |
| `sia_source_error_count` | Gauge | 当前连续错误次数 |
| `sia_source_last_success_timestamp` | Gauge | 最近成功采集时间戳 |
| `sia_source_items_fetched` | Counter | 采集到的情报条数 |
| `sia_source_health_score` | Gauge | 健康评分 0-100 |

### 7.4 批量导入/导出

支持 CSV 格式批量操作：

**导入 CSV 格式示例：**
```csv
name,source_type,content_type,region,language,url,fetch_interval,reliability,authority
"The Hacker News",rss,news_media,global,en,"https://feeds.feedburner.com/TheHackersNews",60,4,4
"FreeBuf",rss,news_media,cn,zh,"https://www.freebuf.com/feed",120,3,3
"CNVD",api,vuln_db,cn,zh,"https://www.cnvd.org.cn/api/v1",240,5,5
```

**API 接口：**
- `POST /api/v1/sources/import` — 批量导入
- `GET /api/v1/sources/export?format=csv` — 批量导出
- 导入前进行格式校验和 URL 可达性预检
- 导入结果返回成功/失败/跳过条数及详细错误信息

---

## 8. 情报采集引擎

### 8.1 采集器架构

```
┌────────────────────────────────────────────────────────────────┐
│                      情报采集引擎                                │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  调度控制器 (Scheduler)                    │  │
│  │  - 读取情报源配置，按 fetch_interval 调度采集任务            │  │
│  │  - 配额控制：检查 daily_used < daily_quota                 │  │
│  │  - 并发控制：按域名限制并发数（同域名最多 2 并发）            │  │
│  │  - 优先级调度：高优先级源优先执行                            │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                             │                                  │
│  ┌──────────────────────────▼───────────────────────────────┐  │
│  │                 采集器工厂 (Collector Factory)              │  │
│  │  根据 source_type 选择对应的采集器实现                       │  │
│  └──────┬──────┬──────┬──────┬──────┬──────┬───────────────┘  │
│         │      │      │      │      │      │                   │
│         ▼      ▼      ▼      ▼      ▼      ▼                   │
│  ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐                  │
│  │ RSS ││ Web ││ API ││WeChat││Dark ││Vuln │                  │
│  │采集器││爬虫 ││采集器││采集器││ Web ││ DB  │                  │
│  └──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘                  │
│     │      │      │      │      │      │                       │
│     └──────┴──────┴──────┴──────┴──────┘                       │
│                    │                                           │
│  ┌─────────────────▼────────────────────────────────────────┐  │
│  │             原始情报标准化处理器                              │  │
│  │  - 提取：标题、正文、发布时间、作者、URL、标签                 │  │
│  │  - 清洗：去除 HTML 标签、广告内容、无关导航                   │  │
│  │  - 语言检测：使用 langdetect/fasttext                       │  │
│  │  - 标准化输出：统一 JSON Schema                             │  │
│  └─────────────────┬────────────────────────────────────────┘  │
│                    │                                           │
│                    ▼                                           │
│             写入 Redis Stream                                  │
│         (raw_intel_stream)                                     │
└────────────────────────────────────────────────────────────────┘
```

### 8.2 各类型采集器详细设计

#### 8.2.1 RSS 采集器

```python
# 伪代码 - RSS 采集器核心逻辑
class RSSCollector:
    """
    采集策略：
    1. 使用 feedparser 解析 RSS/Atom 源
    2. 通过 ETag / Last-Modified 实现增量采集
    3. 按 entry.published 过滤已处理的旧条目
    """

    def collect(self, source: IntelSource) -> list[RawIntel]:
        # 带条件请求头（增量采集）
        feed = feedparser.parse(
            source.url,
            etag=source.last_etag,
            modified=source.last_modified
        )

        if feed.status == 304:  # 无更新
            return []

        entries = []
        for entry in feed.entries:
            if entry.published_parsed <= source.last_fetch_at:
                continue
            entries.append(RawIntel(
                title=entry.title,
                content=entry.summary or entry.content[0].value,
                url=entry.link,
                published_at=entry.published_parsed,
                source_id=source.id,
                source_name=source.name,
                language=detect_language(entry.title + entry.summary)
            ))

        return entries
```

#### 8.2.2 网页爬虫引擎

```python
class WebScraperCollector:
    """
    采集策略：
    1. 使用 Crawl4AI 进行网页抓取和内容提取
    2. 支持 JavaScript 渲染页面（通过 Playwright 后端）
    3. 使用 LLM 提取结构化内容（Crawl4AI 的 LLM extraction 模式）
    4. 遵守 robots.txt
    5. 控制爬取频率，单域名间隔 ≥ 5 秒
    """

    def collect(self, source: IntelSource) -> list[RawIntel]:
        config = source.fetch_method  # JSON 配置

        # Crawl4AI 抓取
        result = crawler.run(
            url=source.url,
            extraction_strategy=LLMExtractionStrategy(
                schema=IntelArticleSchema,
                instruction="提取安全相关的新闻文章标题、摘要、正文和发布日期"
            ),
            js_render=config.get("js_render", False),
            wait_for=config.get("wait_selector"),
            respect_robots_txt=True
        )

        return [self._to_raw_intel(item, source) for item in result.extracted]
```

#### 8.2.3 漏洞数据库采集器

```python
class VulnDBCollector:
    """
    对接数据库：NVD (NIST), CNVD, CNNVD, ExploitDB, GitHub Advisory

    采集策略：
    1. NVD: 使用官方 REST API 2.0，按 lastModStartDate 增量查询
    2. CNVD: 使用其公开 API 或网页抓取
    3. 重点关注 CVSS ≥ 7.0 的漏洞
    4. 对于涉及企业使用技术栈的漏洞，自动标记为高优先级
    """

    def collect_nvd(self, source: IntelSource) -> list[RawIntel]:
        params = {
            "lastModStartDate": source.last_fetch_at.isoformat(),
            "lastModEndDate": datetime.utcnow().isoformat(),
            "cvssV3Severity": "HIGH",  # HIGH + CRITICAL
            "resultsPerPage": 100
        }

        response = self._api_call(source.url, params, source.auth_config)

        vulns = []
        for vuln in response["vulnerabilities"]:
            cve = vuln["cve"]
            cvss_score = self._extract_cvss(cve)

            vulns.append(RawIntel(
                title=f"[CVE] {cve['id']} - {cve['descriptions'][0]['value'][:100]}",
                content=self._format_vuln_detail(cve),
                url=f"https://nvd.nist.gov/vuln/detail/{cve['id']}",
                published_at=cve["published"],
                source_id=source.id,
                intel_type="vulnerability",
                severity=self._cvss_to_severity(cvss_score),
                metadata={
                    "cve_id": cve["id"],
                    "cvss_score": cvss_score,
                    "affected_products": self._extract_cpe(cve),
                    "exploit_available": self._check_exploit(cve["id"])
                }
            ))

        return vulns
```

#### 8.2.4 暗网监控采集器（需求文档未提及，补充）

```python
class DarkWebCollector:
    """
    监控目标：
    1. 暗网论坛中提及本企业名称/品牌的帖子
    2. 数据泄露市场中本企业相关数据的出售信息
    3. 勒索团伙"耻辱墙"上的受害者信息（监控同行业企业）

    安全要求：
    - 所有暗网访问通过隔离的 Tor 代理容器
    - 采集器容器使用独立的网络命名空间
    - 禁止下载任何文件，仅抓取文本
    - 所有采集日志脱敏后存储
    """

    # 通过企业出口代理的 Tor SOCKS5 端口访问
    TOR_PROXY = "socks5h://tor-proxy.internal:9050"

    # 监控关键词（企业名称及变体）
    BRAND_KEYWORDS = [
        "企业全称", "企业英文名", "品牌名", "子公司名",
        "核心产品名", "域名"
    ]
```

#### 8.2.5 社交媒体监控采集器（需求文档未提及，补充）

```python
class SocialMediaCollector:
    """
    监控平台：
    - Twitter/X: 安全研究员 PoC 披露、0day 传播
    - GitHub: Security Advisory, 安全工具新版本
    - Telegram: 安全频道（可选）

    采集策略：
    - Twitter: 通过 Nitter 实例（私有部署）获取 RSS
    - GitHub: 使用 GitHub Advisory API
    - 关注高影响力安全研究员列表（可配置）
    """
```

#### 8.2.6 法规数据库采集器（需求文档隐含，显式补充）

```python
class RegulationCollector:
    """
    监控目标法规数据库：

    欧盟:
    - EUR-Lex (https://eur-lex.europa.eu): EU 法规原文
    - ENISA publications: 欧盟网络安全指南
    - EDPB (European Data Protection Board): GDPR 执法案例

    中国:
    - 中国法规网 / 国家法律法规数据库
    - 工信部公告
    - 国家互联网信息办公室
    - 全国信息安全标准化技术委员会 (TC260)

    东南亚:
    - 新加坡 PDPC (Personal Data Protection Commission)
    - 泰国 PDPA
    - 马来西亚 PDPA / CMA
    - 印尼 PDP Law
    - 越南 Cybersecurity Law

    全球/行业:
    - UNECE WP.29 (UN R155/R156)
    - ISO (21434, 27001 等标准更新)
    - SAE International

    法规变化检测策略：
    1. 定时抓取法规页面快照
    2. 与上次快照进行 diff 比对
    3. 有变化时触发 LLM 分析变化内容和影响
    4. 法规变化自动标记为 P1 级别
    """
```

### 8.3 采集频率控制策略

| 情报源类型 | 默认采集间隔 | 高峰期间隔 | 并发限制 | 说明 |
|-----------|------------|-----------|---------|------|
| RSS 订阅 | 4 小时 | 1 小时 | 同域名 2 并发 | ETag 增量采集 |
| 安全资讯网站 | 12 小时 | 6 小时 | 同域名 1 并发 | 遵守 robots.txt |
| 漏洞数据库 API | 6 小时 | 2 小时 | 2 并发 | API 配额控制 |
| 微信公众号 | 12 小时 | 6 小时 | 3 并发 | 通过 WeRSS |
| 法规数据库 | 24 小时 | 12 小时 | 1 并发 | 变化频率低 |
| 暗网论坛 | 24 小时 | 12 小时 | 1 并发 | 最小化流量 |
| 社交媒体 | 2 小时 | 30 分钟 | 3 并发 | 时效性高 |

**高峰期定义：**
- 重大安全事件发生后 72 小时内（P0/P1 触发）
- 每月微软补丁星期二后 48 小时
- 重大安全会议期间（Black Hat, DEF CON, RSA）

### 8.4 采集原始数据标准化 Schema

```json
{
    "$schema": "RawIntel-v1.0",
    "id": "uuid-v4",
    "source_id": 123,
    "source_name": "The Hacker News",
    "source_type": "rss",

    "title": "原始标题",
    "title_zh": "中文翻译标题（非中文情报）",
    "content": "正文内容（纯文本）",
    "content_zh": "中文翻译内容（非中文情报）",
    "summary": "原始摘要",
    "url": "https://original-article-url",
    "author": "作者",
    "tags": ["标签1", "标签2"],

    "language": "en",
    "published_at": "2026-03-28T10:30:00Z",
    "collected_at": "2026-03-28T11:00:00Z",

    "intel_type": "vulnerability|incident|regulation|research|news|trend",

    "metadata": {
        "cve_id": "CVE-2026-XXXX",
        "cvss_score": 9.8,
        "affected_products": [],
        "related_urls": [],
        "ioc_indicators": []
    },

    "processing_status": "raw|preprocessed|analyzed|published",
    "fingerprint": "sha256-of-title+url (用于精确去重)"
}
```

---

## 9. AI 分析管线

### 9.1 分析管线总览

```
原始情报 (Redis Stream: raw_intel_stream)
    │
    ▼
┌─────────────────────────────────┐
│  Stage 1: 预处理                 │
│  ├─ 内容清洗（去 HTML/广告/噪音）  │
│  ├─ 语言检测                     │
│  ├─ 非中文内容 → LLM 翻译        │
│  ├─ 关键信息提取（NER）           │
│  │   ├─ 组织名称                 │
│  │   ├─ 产品/系统名称             │
│  │   ├─ CVE 编号                 │
│  │   ├─ 地理位置                  │
│  │   ├─ 人名                     │
│  │   └─ 时间表达式                │
│  └─ 向量化（bge-large-zh-v1.5）   │
│                                  │
│  输出 → preprocessed_intel_stream │
└─────────────────┬───────────────┘
                  │
                  ▼
┌─────────────────────────────────┐
│  Stage 2: 去重与事件关联          │
│  ├─ 指纹去重（SHA256 精确匹配）    │
│  ├─ 语义去重（向量相似度 ≥ 0.85）  │
│  ├─ 事件聚合（同一事件多源合并）    │
│  └─ 跨日去重检查                  │
│                                  │
│  输出 → unique_intel_stream      │
└─────────────────┬───────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│ Stage 3a:    │    │ Stage 3b:    │
│ 紧急检测      │    │ 深度分析     │
│ (实时通道)    │    │ (批量通道)   │
│              │    │              │
│ P0/P1 规则    │    │ 情报分类     │
│ 匹配 → 即时   │    │ 价值评分     │
│ 推送          │    │ 影响分析     │
└──────────────┘    │ ATT&CK 映射  │
                    │ 知识图谱更新  │
                    │ LLM 点评生成  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Stage 4:     │
                    │ 报告聚合     │
                    │ 按日/周/月/  │
                    │ 半年/年汇总   │
                    └──────────────┘
```

### 9.2 LLM 分析 Prompt 工程

#### 9.2.1 情报分类 Prompt

```markdown
# 系统角色
你是一位资深的企业安全情报分析师，服务于一家大型跨国智能网联汽车企业。
你需要对安全情报进行专业分类。

# 分类体系
请将以下情报归入最合适的一级分类和二级分类：

一级分类：
1. 安全攻击事件
2. 安全漏洞
3. 数据泄露
4. 法律法规变化
5. 行业安全动态
6. 安全技术研究
7. 供应链安全
8. 安全趋势分析

二级分类（示例）：
- 安全攻击事件 → APT攻击 / 勒索攻击 / DDoS / 钓鱼攻击 / 供应链攻击 / 其他
- 安全漏洞 → 0day / 高危CVE / 中危CVE / 组件漏洞 / 其他
- 数据泄露 → 个人数据 / 企业机密 / 源代码 / 凭证泄露 / 其他
- 法律法规变化 → 新法颁布 / 法规修订 / 执法案例 / 标准更新 / 其他
...

# 输入
情报标题：{title}
情报摘要：{summary}
情报正文（前 2000 字）：{content[:2000]}
情报来源：{source_name}
发布时间：{published_at}

# 输出格式（JSON）
{
    "primary_category": "一级分类名称",
    "secondary_category": "二级分类名称",
    "confidence": 0.95,
    "reasoning": "分类理由（一句话）"
}
```

#### 9.2.2 情报评分 Prompt

```markdown
# 系统角色
你是一位服务于大型跨国智能网联汽车企业的安全情报分析师。
请根据以下维度对情报进行价值评分。

# 评分维度与权重

## 维度 1：企业相关性 (权重 30%)
评估该情报与本企业（智能网联汽车制造商，市场覆盖欧盟/中国/东南亚）的相关程度。
- 10 分：直接涉及本企业或本企业正在使用的系统/产品
- 8 分：涉及智能网联汽车行业
- 6 分：涉及本企业使用的通用 IT 技术栈
- 4 分：涉及同行业其他企业
- 2 分：通用安全信息，间接相关
- 0 分：无关

## 维度 2：威胁严重性 (权重 25%)
评估该威胁的技术严重程度。
- 10 分：可远程利用，无需认证，影响面广（如 RCE 0day）
- 8 分：高危漏洞（CVSS ≥ 9.0）或大规模数据泄露
- 6 分：高危漏洞（CVSS 7.0-8.9）或中等安全事件
- 4 分：中危安全事件或漏洞
- 2 分：低危信息或一般性安全新闻
- 0 分：纯资讯/趋势，无直接威胁

## 维度 3：时效性 (权重 20%)
评估该情报的时间紧迫度。
- 10 分：正在被活跃利用的 0day，需立即响应
- 8 分：24 小时内披露的高危漏洞/攻击事件
- 6 分：本周内的重要安全动态
- 4 分：本月内的安全信息
- 2 分：历史事件回顾或长期趋势
- 0 分：过时信息

## 维度 4：可操作性 (权重 15%)
评估该情报是否能转化为具体安全行动。
- 10 分：包含具体漏洞修复方案/补丁/IoC
- 8 分：包含明确的防御建议
- 6 分：包含攻击特征描述，可用于检测
- 4 分：有参考价值但需进一步调研
- 2 分：仅提供方向性参考
- 0 分：纯资讯，无可操作内容

## 维度 5：信息质量 (权重 10%)
评估情报来源的可靠性和内容质量。
- 10 分：官方权威源（厂商公告、CVE、政府通报）
- 8 分：知名安全研究团队/安全媒体
- 6 分：业内知名个人研究者
- 4 分：一般安全媒体/博客
- 2 分：未经验证的社交媒体信息
- 0 分：来源不明或可疑

# 输入
{intel_data}

# 输出格式（JSON）
{
    "scores": {
        "relevance": {"score": 8, "reason": "涉及车联网 CAN 总线漏洞"},
        "severity": {"score": 9, "reason": "CVSS 9.8，可远程利用"},
        "timeliness": {"score": 10, "reason": "今日披露，已有在野利用"},
        "actionability": {"score": 8, "reason": "厂商已发布补丁"},
        "quality": {"score": 10, "reason": "NVD 官方数据"}
    },
    "total_score": 8.85,
    "priority_level": "P0",
    "tags": ["车联网", "CAN总线", "远程利用", "已有补丁"]
}
```

#### 9.2.3 情报点评生成 Prompt

```markdown
# 系统角色
你是一位服务于大型跨国智能网联汽车企业的资深安全顾问。
请对以下安全情报撰写专业点评，供企业高管和安全团队参考。

# 点评要求
1. 用 2-3 句话简要说明该事件的核心要点
2. 分析对本企业的潜在影响（考虑企业的业务特点：智能网联汽车，市场在欧盟/中国/东南亚）
3. 给出具体的建议行动
4. 关键安全术语保留英文原文

# 点评语气
- 专业、客观、简洁
- 不使用"可能""或许"等模糊表述，直接给出判断
- 如有不确定性，明确标注为"待确认"

# 输入
{intel_data_with_scores}

# 输出格式
**要点：** [核心要点 2-3 句]
**影响分析：** [对本企业的影响评估]
**建议行动：** [具体可执行的建议]
```

#### 9.2.4 态势总评生成 Prompt（日报/周报/月报通用，按 report_type 调整）

```markdown
# 系统角色
你是一位服务于大型跨国智能网联汽车企业的首席安全顾问。
请基于以下{report_period}的安全情报数据，撰写安全态势总评。

# 总评要求
- 日报态势总评：1-2 句话概括当日安全态势
- 周报态势总评：1-2 句话 + 本周重点关注事项
- 月报态势总评：200-300 字深度分析
- 半年报态势总评：500-800 字全面回顾
- 年报态势总评：800-1200 字年度安全态势综述

# AI 洞察要求
基于情报数据进行以下分析：
1. 识别本期出现的新攻击模式或趋势
2. 分析威胁格局的变化方向
3. 评估对本企业所在行业（智能网联汽车）的影响
4. 与上一周期的数据进行对比（如适用）
5. 结合全球地缘政治形势分析安全威胁变化

# 输入数据
{period_intel_summary}

# 输出格式
## 态势总评
[总评内容]

## AI 洞察
[洞察内容]

## 关键数据
- 本期采集情报总量：{total}
- 按类别分布：{category_stats}
- 按严重级别分布：{severity_stats}
- 按地域分布：{region_stats}
```

### 9.3 LLM 调用优化策略

| 策略 | 实现方式 | 目的 |
|------|---------|------|
| **批量处理** | 将多条短情报合并为一次 LLM 调用（每批 5-10 条） | 减少 API 调用次数 |
| **分级分析** | 高分情报用长 Prompt 深度分析，低分情报用短 Prompt 快速处理 | 节省计算资源 |
| **缓存复用** | 对完全相同的输入缓存 LLM 输出（TTL 24h） | 避免重复计算 |
| **异步并行** | 分类/评分/点评三个任务并行调用 LLM | 缩短处理时间 |
| **降级兜底** | LLM 不可用时使用规则引擎进行基础分类和评分 | 保证基础功能 |
| **上下文压缩** | 长文本先提取摘要再进行分析 | 控制 Token 消耗 |

### 9.4 情报处理能力估算

| 指标 | 估算值 | 说明 |
|------|-------|------|
| 每日原始情报量 | 500-1000 条 | 200+ 情报源 |
| 去重后有效情报 | 200-400 条 | 去重率约 50-60% |
| 每条情报 LLM 处理 Token | ~3000 tokens (输入+输出) | 分类+评分+点评 |
| 每日 LLM Token 消耗 | ~100 万 tokens | 包含报告生成 |
| 每日 LLM 调用次数 | ~500-800 次 | 批量处理后 |
| 预处理阶段耗时 | ~1 小时 | 含翻译 |
| 深度分析阶段耗时 | ~2 小时 | 含评分和点评 |
| 报告生成阶段耗时 | ~30 分钟 | 含模板渲染 |

---

## 10. 去重与事件追踪引擎

### 10.1 三级去重架构

```
                原始情报
                   │
                   ▼
        ┌─────────────────────┐
        │  Level 1: 精确去重   │
        │  SHA256(title+url)  │
        │  → 完全相同的条目    │
        │  → 直接丢弃          │
        └─────────┬───────────┘
                  │ 通过
                  ▼
        ┌─────────────────────┐
        │  Level 2: 语义去重   │
        │  向量相似度计算       │
        │  Cosine Sim ≥ 0.85  │
        │  → 保留信息最完整/   │
        │    最权威的版本       │
        │  → 合并其他源为"     │
        │    相关报道"引用      │
        └─────────┬───────────┘
                  │ 通过
                  ▼
        ┌─────────────────────┐
        │  Level 3: 跨日去重   │
        │  与近 7 日已推送情报  │
        │  进行语义比对         │
        │  Sim ≥ 0.80          │
        │  → 检查是否有重大更新 │
        │    ├─ 有更新 → 标记   │
        │    │   为"跟踪更新"   │
        │    └─ 无更新 → 跳过   │
        └─────────┬───────────┘
                  │
                  ▼
            唯一有效情报
```

### 10.2 事件追踪聚合机制

```
┌────────────────────────────────────────────────────────────────┐
│                      事件追踪引擎                                │
│                                                                │
│  事件生命周期管理：                                               │
│                                                                │
│  新情报 ──┬── 与现有事件主线匹配？                                │
│           │                                                    │
│           ├─ 是 → 合并入现有事件主线                              │
│           │       ├─ 更新事件时间轴                               │
│           │       ├─ 更新最新状态                                 │
│           │       ├─ 计算事件热度变化                              │
│           │       └─ 判断是否有"重大更新"                          │
│           │           ├─ 是 → 标记需推送更新                      │
│           │           └─ 否 → 仅入库存档                         │
│           │                                                    │
│           └─ 否 → 创建新事件主线                                  │
│                   ├─ event_id = UUID                            │
│                   ├─ timeline = [{当前情报}]                     │
│                   ├─ status = "developing" | "resolved"         │
│                   └─ heat_score = 初始热度                       │
│                                                                │
│  事件主线数据结构：                                               │
│  {                                                             │
│    "event_id": "evt-uuid",                                     │
│    "event_title": "SolarWinds 供应链攻击事件",                    │
│    "status": "developing",                                     │
│    "first_seen": "2026-03-25T10:00:00Z",                       │
│    "last_updated": "2026-03-28T08:00:00Z",                     │
│    "heat_score": 95,                                           │
│    "related_intel_ids": [101, 105, 112, 118],                  │
│    "timeline": [                                               │
│      {"date": "03-25", "summary": "首次披露..."},                │
│      {"date": "03-26", "summary": "影响范围扩大..."},            │
│      {"date": "03-27", "summary": "厂商发布补丁..."},            │
│      {"date": "03-28", "summary": "攻击者身份确认..."}           │
│    ],                                                          │
│    "current_summary": "最新状态综述...",                         │
│    "affected_entities": ["SolarWinds", "Microsoft", ...],       │
│    "mitre_techniques": ["T1195.002", "T1059.001"]              │
│  }                                                             │
│                                                                │
│  事件归档规则：                                                   │
│  - 连续 7 天无新情报 → status = "cooling_down"                   │
│  - 连续 30 天无新情报 → status = "archived"                      │
│  - 已有官方修复/结论 → status = "resolved"                       │
└────────────────────────────────────────────────────────────────┘
```

### 10.3 "重大更新"判定规则

LLM 判定一条与已有事件关联的情报是否构成"重大更新"：

| 条件 | 示例 | 判定 |
|------|------|------|
| 影响范围显著扩大 | 从单个产品扩展到整个产品线 | 重大更新 ✅ |
| 攻击者身份确认 | 国家级 APT 组织归因 | 重大更新 ✅ |
| 官方补丁/修复发布 | 厂商发布安全更新 | 重大更新 ✅ |
| PoC/Exploit 公开 | 漏洞利用代码公开 | 重大更新 ✅ |
| 法律/监管介入 | 政府调查/罚款 | 重大更新 ✅ |
| 受害企业数量显著增加 | 从 10 家 → 1000 家 | 重大更新 ✅ |
| 仅增加相同信息源 | 另一家媒体报道相同内容 | 非重大更新 ❌ |
| 微小细节补充 | 增加少量技术细节 | 非重大更新 ❌ |

---

## 11. 情报评分与分级模型

### 11.1 评分模型架构

```
┌────────────────────────────────────────────────────────────────┐
│                      情报评分引擎                                │
│                                                                │
│  输入：经预处理和去重的标准化情报                                   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    LLM 多维评分                           │  │
│  │                                                          │  │
│  │  企业相关性 ────── 30% ──┐                                │  │
│  │  威胁严重性 ────── 25% ──┤                                │  │
│  │  时效性 ────────── 20% ──┼──→ 加权总分 (0-10)             │  │
│  │  可操作性 ────────  15% ──┤                                │  │
│  │  信息质量 ────────  10% ──┘                                │  │
│  │                                                          │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                             │                                  │
│  ┌──────────────────────────▼───────────────────────────────┐  │
│  │                    优先级映射                              │  │
│  │                                                          │  │
│  │  总分 ≥ 8.5 ──→ P0（紧急）                                │  │
│  │  总分 6.0-8.4 ──→ P1（重要）                              │  │
│  │  总分 3.0-5.9 ──→ P2（常规，纳入日报）                     │  │
│  │  总分 < 3.0 ──→ P3（低价值，仅归档）                       │  │
│  │                                                          │  │
│  │  特殊规则覆写：                                            │  │
│  │  - 包含本企业名称/产品 → 强制 P0                           │  │
│  │  - 包含 "0day" + "在野利用" → 强制 P0                     │  │
│  │  - 法规变化涉及目标市场 → 至少 P1                          │  │
│  │  - CVSS ≥ 9.0 且影响企业使用产品 → 强制 P0                 │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                             │                                  │
│  ┌──────────────────────────▼───────────────────────────────┐  │
│  │                    日报入选筛选                             │  │
│  │                                                          │  │
│  │  1. P0/P1 情报全部入选                                    │  │
│  │  2. P2 情报按总分降序排列                                  │  │
│  │  3. 确保各分类至少有 1 条代表性情报                          │  │
│  │  4. 总数控制在 ≤ 10 条（日报）/ ≤ 20 条（月报及以上）         │  │
│  │  5. 同类情报超过 3 条时只保留 Top 3                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 11.2 评分维度权重可配置

评分维度和权重存储在数据库中，通过管理界面可调整：

```sql
CREATE TABLE scoring_config (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    dimension       VARCHAR(50) NOT NULL COMMENT '维度名称',
    weight          DECIMAL(3,2) NOT NULL COMMENT '权重 (0.00-1.00)',
    scoring_rules   JSON NOT NULL COMMENT '评分细则',
    is_active       BOOLEAN DEFAULT TRUE,
    version         INT DEFAULT 1 COMMENT '版本号',
    updated_by      VARCHAR(100),
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_dimension_version (dimension, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 特殊规则覆写表
CREATE TABLE scoring_overrides (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    rule_name       VARCHAR(100) NOT NULL,
    condition_type  ENUM('keyword_match', 'cvss_threshold', 'source_match',
                         'entity_match', 'regex_match') NOT NULL,
    condition_value JSON NOT NULL,
    override_level  ENUM('P0', 'P1', 'P2') NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_by      VARCHAR(100),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 11.3 情报筛选策略

#### 日报筛选（≤ 10 条）

```
1. 必选池：
   - 所有 P0 情报（无上限，但通常 0-2 条/天）
   - 所有 P1 情报（上限 5 条，超出按分数截断）

2. 补选池（填充至 10 条）：
   - 从 P2 情报中按总分排序
   - 确保至少覆盖以下分类各 1 条（如有）：
     a. 漏洞类
     b. 攻击事件类
     c. 法规变化类
     d. 行业动态类
   - 同一事件主线的情报只取最新一条

3. 排序：
   - P0 → P1 → P2
   - 同级别内按总分降序
```

#### 周报/月报/半年报/年报筛选（≤ 20 条）

```
1. 回顾本周期内所有日报中推送的 P0/P1 情报
2. 合并事件主线，提取关键节点
3. 补充日报未覆盖但有长期意义的 P2 情报（趋势类、法规类）
4. LLM 生成周期性洞察和趋势分析
5. 总数控制在 ≤ 20 条
```

---

## 12. 知识图谱与实体关联

### 12.1 知识图谱设计（需求文档未提及，补充）

知识图谱用于建立安全实体之间的关联关系，提升情报分析的深度。

```
┌────────────────────────────────────────────────────────────────┐
│                      安全知识图谱                                │
│                                                                │
│  实体类型 (Nodes):                                              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │ 组织       │  │ 产品/系统  │  │ 漏洞       │  │ 攻击组织   │   │
│  │ (Org)     │  │ (Product) │  │ (Vuln)    │  │ (Threat   │   │
│  │           │  │           │  │           │  │  Actor)   │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
│  │ 安全事件   │  │ 法规       │  │ 技术/工具  │  │ 地域       │   │
│  │ (Event)   │  │(Regulation)│ │ (Tech)    │  │ (Region)  │   │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘   │
│                                                                │
│  关系类型 (Edges):                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  组织 ─[uses]→ 产品                                      │   │
│  │  组织 ─[suffered]→ 安全事件                               │   │
│  │  组织 ─[supplies_to]→ 组织                                │   │
│  │  组织 ─[regulated_by]→ 法规                               │   │
│  │  漏洞 ─[affects]→ 产品                                    │   │
│  │  漏洞 ─[exploited_in]→ 安全事件                            │   │
│  │  漏洞 ─[discovered_by]→ 组织/人                            │   │
│  │  攻击组织 ─[attributed_to]→ 安全事件                       │   │
│  │  攻击组织 ─[uses]→ 技术/工具                               │   │
│  │  攻击组织 ─[targets]→ 行业/地域                            │   │
│  │  安全事件 ─[occurred_in]→ 地域                             │   │
│  │  法规 ─[applies_to]→ 地域                                 │   │
│  │  法规 ─[impacts]→ 行业/产品                                │   │
│  │  产品 ─[component_of]→ 产品（组件依赖关系）                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  Neo4j 示例查询：                                               │
│                                                                │
│  // 查找影响本企业供应链的所有漏洞                                 │
│  MATCH (our:Org {name: "本企业"})                               │
│        <-[:supplies_to]-(supplier:Org)                          │
│        -[:uses]->(product:Product)                              │
│        <-[:affects]-(vuln:Vuln)                                 │
│  WHERE vuln.cvss >= 7.0                                        │
│  RETURN supplier.name, product.name, vuln.cve_id, vuln.cvss    │
│                                                                │
│  // 查找某 APT 组织的完整攻击画像                                 │
│  MATCH (apt:ThreatActor {name: "APT41"})                       │
│        -[r]->(target)                                          │
│  RETURN apt, type(r), target                                   │
└────────────────────────────────────────────────────────────────┘
```

### 12.2 实体提取流程

```
原始情报文本
     │
     ▼
┌──────────────────────────┐
│  LLM 命名实体识别 (NER)   │
│                          │
│  提取实体：               │
│  - 组织名称               │
│  - 产品/系统名称           │
│  - CVE 编号               │
│  - 攻击组织名称            │
│  - 地理位置               │
│  - 法规名称               │
│  - 技术/工具名称           │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  实体消歧与归一化          │
│                          │
│  "微软" = "Microsoft"    │
│  = "MSFT" = "微软公司"   │
│  → 统一为 org:microsoft  │
│                          │
│  使用别名表 + LLM 辅助    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  关系抽取                 │
│                          │
│  LLM 从文本中抽取实体     │
│  之间的关系               │
│  输出 (entity1, rel,     │
│        entity2) 三元组    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  写入 Neo4j 知识图谱      │
│                          │
│  MERGE 防止重复节点       │
│  ON MATCH 更新属性        │
│  ON CREATE 初始化属性     │
└──────────────────────────┘
```

### 12.3 知识图谱应用场景

| 场景 | 查询方式 | 价值 |
|------|---------|------|
| **供应链风险溯源** | 从供应商安全事件追溯影响本企业的路径 | 快速评估供应链风险传导 |
| **攻击组织画像** | 聚合 APT 组织的目标行业、使用技术、活跃地域 | 威胁情报驱动的防御 |
| **漏洞影响评估** | 从漏洞出发关联受影响产品和使用这些产品的组织 | 精准漏洞响应 |
| **法规合规图谱** | 法规 → 适用地域 → 影响业务 → 所需行动 | 合规差距分析 |
| **安全事件关联** | 多个看似独立的事件是否源自同一攻击组织 | 发现隐蔽关联 |
| **趋势发现** | 时间维度上实体关系的演变 | 预判未来威胁方向 |

---

## 13. MITRE ATT&CK 映射

### 13.1 设计目标（需求文档未提及，补充）

将安全情报自动映射到 MITRE ATT&CK 框架，提供标准化的攻击技术分类和防御指导。

### 13.2 映射流程

```
安全情报（攻击事件/漏洞利用类）
     │
     ▼
┌──────────────────────────────────────────┐
│  LLM ATT&CK 映射 Prompt                  │
│                                          │
│  输入：情报标题 + 摘要 + 正文              │
│                                          │
│  任务：                                   │
│  1. 识别涉及的攻击战术 (Tactics)            │
│     - Initial Access, Execution,          │
│       Persistence, Privilege Escalation,  │
│       Defense Evasion, Credential Access, │
│       Discovery, Lateral Movement,        │
│       Collection, C2, Exfiltration,       │
│       Impact                              │
│                                          │
│  2. 识别具体攻击技术 (Techniques)           │
│     - 如 T1566.001 (Phishing: Attachment) │
│                                          │
│  3. 识别涉及的软件/工具                     │
│     - 如 S0154 (Cobalt Strike)            │
│                                          │
│  4. 关联防御建议                            │
│     - 对应的 Mitigations (M-codes)        │
│     - 对应的检测方法 (Detection)            │
│                                          │
│  输出格式 (JSON):                          │
│  {                                       │
│    "tactics": ["TA0001"],                │
│    "techniques": [                       │
│      {                                   │
│        "id": "T1195.002",               │
│        "name": "Supply Chain Compromise: │
│                 Compromise Software       │
│                 Supply Chain",            │
│        "confidence": 0.9                 │
│      }                                   │
│    ],                                    │
│    "software": ["S0154"],                │
│    "mitigations": ["M1051", "M1016"],    │
│    "detection_suggestions": [            │
│      "监控软件更新来源的完整性校验",          │
│      "部署 EDR 检测异常进程行为"             │
│    ]                                     │
│  }                                       │
└──────────────────────────────────────────┘
```

### 13.3 ATT&CK 本地知识库

在 MySQL 中维护 ATT&CK 框架数据（定期从 MITRE STIX 数据同步）：

```sql
CREATE TABLE mitre_attack (
    id              VARCHAR(20) PRIMARY KEY COMMENT 'T/TA/S/M 编号',
    type            ENUM('tactic', 'technique', 'sub_technique', 'software',
                         'group', 'mitigation') NOT NULL,
    name            VARCHAR(200) NOT NULL,
    name_zh         VARCHAR(200) COMMENT '中文名称',
    description     TEXT,
    description_zh  TEXT COMMENT '中文描述',
    platforms       JSON COMMENT '适用平台',
    data_sources    JSON COMMENT '检测数据源',
    url             VARCHAR(500),
    last_synced_at  DATETIME,

    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ATT&CK 关系表
CREATE TABLE mitre_attack_relations (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    source_id       VARCHAR(20) NOT NULL,
    target_id       VARCHAR(20) NOT NULL,
    relation_type   ENUM('uses', 'mitigates', 'subtechnique_of', 'attributed_to') NOT NULL,

    INDEX idx_source (source_id),
    INDEX idx_target (target_id),
    FOREIGN KEY (source_id) REFERENCES mitre_attack(id),
    FOREIGN KEY (target_id) REFERENCES mitre_attack(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 13.4 应用价值

- **报告增值：** 在安全报告中附带 ATT&CK 映射，让安全运营团队可以直接对照检测规则
- **防御差距分析：** 累积映射数据后，可分析企业面临的高频攻击技术，评估现有防御是否覆盖
- **趋势可视化：** ATT&CK 热力图展示各时期最活跃的攻击技术
- **SOC 联动：** ATT&CK 技术编号可直接对应 SIEM 检测规则

---

## 14. 报告生成子系统

### 14.1 报告类型与推送时间

| 报告 | 推送时间 | 覆盖范围 | 输出版本 |
|------|---------|---------|---------|
| 日报 | 每日 08:00（工作日） | 前日 08:00 至当日 08:00 | 高管简版 + 运营详版 |
| 周报 | 每周五 14:00 | 本周一 00:00 至周五 12:00 | 高管简版 + 运营详版 |
| 月报 | 每月最后一个工作日 08:00 | 当月 1 日至推送日 | 高管简版 + 运营详版 |
| 季度报 | 季末月最后工作日 14:00 | 当季度全部 | 高管简版 + 运营详版 |
| 半年报 | 7 月第 1 个工作日 08:00 | 1月1日 至 6月30日 | 高管简版 + 运营详版 |
| 年报 | 12 月第 3 周周一 08:00 | 1月1日 至推送日 | 高管简版 + 运营详版 |

### 14.2 报告模板体系

#### 14.2.1 日报 — 高管简版模板

```
┌─────────────────────────────────────────────────────────┐
│              🛡️ 安全情报日报（高管版）                      │
│              {date} | 第 {seq} 期                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ■ 今日态势总评                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │  {LLM 生成 1-2 句态势总评}                        │    │
│  │  安全态势灯：🔴严峻 / 🟡警惕 / 🟢平稳              │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ■ 今日关键情报 TOP {n}                                  │
│  ┌─────────────────────────────────────────────────┐    │
│  │  1. [P0] {情报标题}                               │    │
│  │     要点：{LLM 点评 2-3 句}                        │    │
│  │     建议行动：{具体建议}                            │    │
│  │                                                   │    │
│  │  2. [P1] {情报标题}                               │    │
│  │     要点：{LLM 点评 2-3 句}                        │    │
│  │     建议行动：{具体建议}                            │    │
│  │                                                   │    │
│  │  ...                                              │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ■ AI 洞察                                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │  {LLM 生成 3-5 句 AI 洞察分析}                    │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ■ 数据概览                                             │
│  ┌─────────────────────────────────────────────────┐    │
│  │  今日采集：{n} 条 | 入选：{m} 条                    │    │
│  │  漏洞：{x} | 事件：{y} | 法规：{z} | 动态：{w}      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  📎 查看运营详版报告：{link}                              │
│  💬 反馈：{feedback_link}                                │
├─────────────────────────────────────────────────────────┤
│  安全洞察与情报分析智能体 (SIA) | 自动生成                  │
│  分发等级：{distribution_level}                           │
└─────────────────────────────────────────────────────────┘
```

#### 14.2.2 日报 — 运营详版模板

```
┌─────────────────────────────────────────────────────────────┐
│            🛡️ 安全情报日报（运营详版）                         │
│            {date} | 第 {seq} 期                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ■ 态势总评与 AI 洞察                                        │
│  {LLM 生成态势总评和洞察，3-5 句}                              │
│                                                             │
│  ■ P0/P1 紧急情报                                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  编号：INT-{date}-001                                │    │
│  │  级别：P0 🔴                                         │    │
│  │  分类：安全漏洞 > 0day                                │    │
│  │  标题：{完整标题}                                      │    │
│  │  来源：{source_name} | {published_at}                │    │
│  │                                                     │    │
│  │  摘要：                                              │    │
│  │  {LLM 生成的详细摘要}                                 │    │
│  │                                                     │    │
│  │  影响分析：                                           │    │
│  │  {LLM 生成的影响分析}                                  │    │
│  │                                                     │    │
│  │  ATT&CK 映射：{T-codes}                              │    │
│  │                                                     │    │
│  │  建议行动：                                           │    │
│  │  1. {行动1}                                          │    │
│  │  2. {行动2}                                          │    │
│  │                                                     │    │
│  │  参考链接：{urls}                                     │    │
│  │  评分：{total_score} (相关性:{x} 严重性:{y} ...)      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ■ P2 常规情报                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  {按分类分组展示，每条含摘要、点评和参考链接}              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ■ 活跃事件追踪                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  {持续发酵的事件主线，含时间轴更新}                      │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ■ 统计数据                                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  采集总量：{n} | 去重后：{m} | 入选：{k}               │    │
│  │  按类别：{饼图数据}                                    │    │
│  │  按来源：{柱状图数据}                                   │    │
│  │  按地域：{热力图数据}                                   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ■ 情报源健康状态                                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  正常：{n} | 异常：{m} | 暂停：{k}                     │    │
│  │  {异常源列表}                                          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  📎 附件：{本期原始情报清单 CSV}                              │
│  💬 反馈：{feedback_link}                                    │
├─────────────────────────────────────────────────────────────┤
│  SIA | 分发等级：{distribution_level} | {disclaimer}         │
└─────────────────────────────────────────────────────────────┘
```

#### 14.2.3 月报/半年报/年报额外板块

月报及以上级别的报告在日报模板基础上增加以下板块：

```
■ 专项分析（各 300-800 字，由 LLM 生成）
  ├── 企业 IT 安全态势分析
  ├── 车联网与自动驾驶安全分析
  ├── 供应链安全分析
  ├── 全球法规合规变化分析
  ├── 数据泄露态势分析
  └── 新兴威胁与技术分析

■ 趋势分析与预测
  ├── 本期威胁趋势图表（月度/季度环比）
  ├── ATT&CK 热力图（本期最活跃技术）
  ├── 预测：未来 {period} 重点关注方向
  └── 与上期对比分析

■ 战略建议（月报 3 条 / 半年报 3-5 条 / 年报 5-8 条）
  ├── 短期行动建议（1-3 个月）
  ├── 中期规划建议（3-6 个月）
  └── 长期战略建议（6-12 个月）

■ 数据附录
  ├── 本期完整情报清单
  ├── CVE 漏洞清单（与企业技术栈关联）
  ├── 法规变化追踪表
  └── 供应链安全事件追踪表
```

### 14.3 报告渲染与输出格式

| 渠道 | 输出格式 | 渲染技术 |
|------|---------|---------|
| 企业微信 | Markdown 卡片 | 企微 Bot Webhook API |
| 飞书 | 交互式卡片 | 飞书 Bot API (Card JSON) |
| 邮件 | HTML 邮件 + PDF 附件 | Jinja2 HTML 模板 + WeasyPrint PDF |
| Web 控制台 | 在线阅读 | Vue 组件渲染 |
| 存档 | PDF + JSON | WeasyPrint + 原始数据 |

### 14.4 报告生成流程（Dify Workflow）

```
WF-REPORT-DAILY:
  │
  ├─ Node 1: 数据查询
  │  ├─ 查询当日去重后情报
  │  ├─ 查询当日 P0/P1 情报
  │  ├─ 查询活跃事件主线
  │  └─ 查询情报源健康状态
  │
  ├─ Node 2: 情报筛选
  │  ├─ 执行日报筛选策略
  │  └─ 确认入选 ≤ 10 条
  │
  ├─ Node 3: LLM 批量生成
  │  ├─ 态势总评生成
  │  ├─ AI 洞察生成
  │  ├─ 各条情报点评生成（并行）
  │  └─ 统计数据汇总
  │
  ├─ Node 4: 模板渲染
  │  ├─ 高管简版渲染
  │  └─ 运营详版渲染
  │
  ├─ Node 5: 质量检查
  │  ├─ 字数检查（高管版 ≤ 1 页）
  │  ├─ 格式检查
  │  └─ 敏感信息检查
  │
  ├─ Node 6: 报告存档
  │  ├─ 写入数据库
  │  └─ PDF 存入 MinIO
  │
  └─ Node 7: 触发推送
     └─ 发送事件到 WF-PUSH
```

### 14.5 分发等级管理（需求文档 11.2 扩展）

| 分发等级 | 标记 | 推送范围 | 触发条件 |
|---------|------|---------|---------|
| **TLP:RED** | 仅限指定人员 | CISO + 指定人员 | 涉及本企业的 0day、内部泄露 |
| **TLP:AMBER** | 仅限安全团队 | CISO + 安全运营团队 | 未公开漏洞、敏感攻击细节 |
| **TLP:GREEN** | 内部可分享 | 全部订阅人员 | 常规安全情报 |
| **TLP:CLEAR** | 公开 | 全部 + 可外传 | 公开安全资讯 |

分发等级由 LLM 在分析阶段判定，规则：
- 包含本企业名称/内部信息 → TLP:RED
- 包含未公开漏洞（0day）→ TLP:AMBER
- 包含行业敏感信息 → TLP:AMBER
- 其他 → TLP:GREEN

---

## 15. 紧急情报响应机制

### 15.1 P0/P1/P2/P3 四级响应

| 等级 | 触发条件 | 响应时效 | 推送对象 | 推送渠道 |
|------|---------|---------|---------|---------|
| **P0** | 直接关联本企业的攻击/泄露/0day；影响本企业产品的在野利用漏洞 | ≤ 15 分钟 | CISO、CTO、相关业务线负责人 | 企微 + 飞书 + 短信 + 邮件 |
| **P1** | 行业重大安全事件；供应链相关事件；重大法规突变；通用IT高危漏洞 | ≤ 4 小时 | CISO、安全运营、相关业务线 | 企微 + 飞书 + 邮件 |
| **P2** | 常规安全动态 | 纳入日报 | 全部订阅人员 | 企微 + 飞书 + 邮件 |
| **P3** | 低价值信息 | 仅归档 | 无 | 无 |

### 15.2 紧急情报处理流程

```
新情报入库
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  紧急检测引擎 (WF-EMERGENCY)                          │
│  实时运行，不等待批量分析                               │
│                                                      │
│  检测规则（按优先级执行）：                               │
│                                                      │
│  Rule 1: 企业名称精确匹配                              │
│  ├─ 标题/正文包含本企业名称/品牌/产品名                   │
│  └─ → 强制 P0                                        │
│                                                      │
│  Rule 2: 0day + 在野利用关键词                         │
│  ├─ "0day" AND ("in the wild" | "actively exploited"  │
│  │   | "在野利用" | "活跃利用")                          │
│  └─ → P0（影响企业技术栈）/ P1（不影响）                  │
│                                                      │
│  Rule 3: CVSS ≥ 9.0 + 企业使用产品                     │
│  ├─ 高危漏洞 + CPE 匹配企业资产清单                      │
│  └─ → P0                                             │
│                                                      │
│  Rule 4: 行业关键词 + 严重事件特征                       │
│  ├─ "车联网" | "自动驾驶" | "OTA" + "攻击" | "漏洞"     │
│  └─ → P1                                             │
│                                                      │
│  Rule 5: 供应链关键词                                   │
│  ├─ 包含企业已知供应商名称 + "安全事件" | "数据泄露"       │
│  └─ → P1                                             │
│                                                      │
│  Rule 6: 法规突变关键词                                 │
│  ├─ "新法颁布" | "重大修订" + 目标市场（EU/CN/SEA）       │
│  └─ → P1                                             │
│                                                      │
│  无匹配 → 进入常规分析通道                               │
└──────────────┬───────────────────────────────────────┘
               │ P0/P1 检出
               ▼
┌──────────────────────────────────────────────────────┐
│  紧急分析与推送 (WF-EMERGENCY-PUSH)                    │
│                                                      │
│  1. LLM 快速分析（5 分钟内完成）                         │
│     ├─ 简要事件描述                                    │
│     ├─ 影响面评估                                      │
│     └─ 建议应急措施                                    │
│                                                      │
│  2. 人工确认环节（可选，P0 可跳过）                       │
│     ├─ 推送预览给 SOC 值班人员                          │
│     └─ 等待确认（超时 5 分钟自动推送）                    │
│                                                      │
│  3. 多渠道即时推送                                      │
│     ├─ 企业微信 → 目标群/个人                           │
│     ├─ 飞书 → 目标群/个人                              │
│     ├─ 短信 → CISO/CTO（仅 P0）                       │
│     └─ 邮件 → 目标邮件列表                              │
│                                                      │
│  4. 创建事件追踪主线                                    │
│                                                      │
│  5. 记录推送日志                                       │
└──────────────────────────────────────────────────────┘
```

### 15.3 企业资产清单匹配（需求文档未提及，补充）

为精准判断漏洞与企业的关联性，维护企业核心资产清单：

```sql
CREATE TABLE enterprise_assets (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    asset_type      ENUM('os', 'middleware', 'database', 'application', 'framework',
                         'library', 'hardware', 'cloud_service', 'vehicle_platform') NOT NULL,
    vendor          VARCHAR(200) NOT NULL COMMENT '厂商',
    product         VARCHAR(200) NOT NULL COMMENT '产品名',
    version_range   VARCHAR(100) COMMENT '使用版本范围',
    cpe_id          VARCHAR(500) COMMENT 'CPE 标识符',
    department      VARCHAR(200) COMMENT '使用部门/业务线',
    criticality     ENUM('critical', 'high', 'medium', 'low') DEFAULT 'medium',
    notes           TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_vendor_product (vendor, product),
    INDEX idx_cpe (cpe_id),
    INDEX idx_criticality (criticality)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

当新漏洞（CVE）入库时，自动与企业资产清单进行 CPE 匹配，匹配命中则升级优先级。

### 15.4 企业供应商名录匹配（需求文档未提及，补充）

```sql
CREATE TABLE supply_chain_vendors (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    vendor_name     VARCHAR(200) NOT NULL,
    vendor_name_en  VARCHAR(200),
    vendor_aliases  JSON COMMENT '别名列表',
    tier            ENUM('tier1', 'tier2', 'tier3') NOT NULL,
    category        ENUM('chip', 'ecu', 'sensor', 'software', 'cloud', 'other') NOT NULL,
    products_used   JSON COMMENT '我方使用的产品列表',
    risk_level      ENUM('critical', 'high', 'medium', 'low') DEFAULT 'medium',
    is_active       BOOLEAN DEFAULT TRUE,
    updated_at      DATETIME ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_vendor (vendor_name),
    INDEX idx_tier (tier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

情报中提及供应商名录中的企业名时，自动标记为供应链相关情报并升级优先级。

---

## 16. 通知与分发子系统

### 16.1 多渠道推送架构

```
┌─────────────────────────────────────────────────────┐
│                  通知分发服务                          │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │              推送调度器                         │  │
│  │  - 接收报告生成完成事件                          │  │
│  │  - 查询推送目标配置                              │  │
│  │  - 按渠道拆分推送任务                            │  │
│  │  - 写入推送任务队列 (Redis Stream)               │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │                              │
│   ┌──────────────────┼──────────────────────┐       │
│   │                  │                      │       │
│   ▼                  ▼                      ▼       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ 企微推送  │  │ 飞书推送  │  │ 邮件推送  │          │
│  │ Worker   │  │ Worker   │  │ Worker   │          │
│  ├──────────┤  ├──────────┤  ├──────────┤          │
│  │ Webhook  │  │ Bot API  │  │ SMTP     │          │
│  │ API      │  │          │  │          │          │
│  │ 卡片消息  │  │ 交互卡片  │  │ HTML邮件  │          │
│  │ Markdown │  │ Markdown │  │ PDF附件   │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│                                     │               │
│                              ┌──────┴──────┐        │
│                              │ 短信推送     │        │
│                              │ Worker      │        │
│                              ├─────────────┤        │
│                              │ SMS API     │        │
│                              │ (仅 P0)     │        │
│                              └─────────────┘        │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │              推送状态追踪                       │  │
│  │  - 记录每次推送的状态（成功/失败/已读）           │  │
│  │  - 失败重试（最多 3 次）                        │  │
│  │  - 推送送达率统计                               │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 16.2 推送目标管理

```sql
-- 订阅者表
CREATE TABLE subscribers (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(100) NOT NULL,
    role            VARCHAR(100) COMMENT '职位/角色',
    department      VARCHAR(100),

    -- 渠道标识
    wechat_work_id  VARCHAR(200) COMMENT '企业微信 UserID',
    feishu_id       VARCHAR(200) COMMENT '飞书 UserID',
    email           VARCHAR(200),
    phone           VARCHAR(20) COMMENT '手机号（用于短信）',

    -- 订阅配置
    subscribe_level ENUM('all', 'p0_p1_only', 'daily', 'weekly', 'monthly') DEFAULT 'all',
    subscribe_version ENUM('executive', 'operational', 'both') DEFAULT 'executive',
    preferred_channel ENUM('wechat_work', 'feishu', 'email') DEFAULT 'wechat_work',

    -- 分发等级权限
    max_tlp_level   ENUM('RED', 'AMBER', 'GREEN', 'CLEAR') DEFAULT 'GREEN',

    is_active       BOOLEAN DEFAULT TRUE,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_role (role),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 推送组（如 "CISO 直报组"、"安全运营组"、"全员订阅组"）
CREATE TABLE push_groups (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    group_name      VARCHAR(100) NOT NULL,
    description     TEXT,
    trigger_levels  JSON NOT NULL COMMENT '触发的情报级别，如 ["P0","P1"]',
    report_types    JSON NOT NULL COMMENT '接收的报告类型，如 ["daily","weekly"]',
    channels        JSON NOT NULL COMMENT '推送渠道，如 ["wechat_work","email"]',
    is_active       BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 推送组成员关联表
CREATE TABLE push_group_members (
    group_id        INT NOT NULL,
    subscriber_id   INT NOT NULL,
    PRIMARY KEY (group_id, subscriber_id),
    FOREIGN KEY (group_id) REFERENCES push_groups(id),
    FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 16.3 企业微信交互式卡片设计

```json
{
    "msgtype": "template_card",
    "template_card": {
        "card_type": "text_notice",
        "source": {
            "icon_url": "https://internal/sia/icon.png",
            "desc": "安全情报日报",
            "desc_color": 0
        },
        "main_title": {
            "title": "🛡️ 安全情报日报 - 2026-03-28",
            "desc": "态势：🟡警惕 | 入选：8 条"
        },
        "emphasis_content": {
            "title": "1",
            "desc": "P0 紧急情报"
        },
        "sub_title_text": "{LLM 态势总评 1-2 句}",
        "horizontal_content_list": [
            {"keyname": "漏洞", "value": "3 条"},
            {"keyname": "事件", "value": "2 条"},
            {"keyname": "法规", "value": "1 条"},
            {"keyname": "动态", "value": "2 条"}
        ],
        "card_action": {
            "type": 1,
            "url": "https://sia.internal/reports/daily/2026-03-28"
        },
        "button_list": [
            {"text": "查看详情", "type": 1, "url": "https://sia.internal/reports/..."},
            {"text": "有价值 👍", "type": 2, "key": "feedback_useful_20260328"},
            {"text": "无价值 👎", "type": 2, "key": "feedback_useless_20260328"}
        ]
    }
}
```

---

## 17. Web 控制台与查询系统

### 17.1 功能模块

```
┌─────────────────────────────────────────────────────────────┐
│                    SIA Web 控制台                             │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 导航栏                                                 │  │
│  │  仪表盘 | 情报中心 | 报告中心 | 情报源管理 |              │  │
│  │  关键词管理 | 知识图谱 | 反馈统计 | 系统设置              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  📊 仪表盘 (Dashboard)                                      │
│  ├── 今日安全态势灯（红/黄/绿）                               │
│  ├── 今日情报统计（采集量/去重量/入选量）                       │
│  ├── P0/P1 待处理情报队列                                    │
│  ├── 活跃事件追踪看板                                        │
│  ├── 近 30 天情报趋势图                                      │
│  ├── ATT&CK 热力图                                          │
│  ├── 情报源健康状态概览                                       │
│  └── 最近推送记录                                            │
│                                                             │
│  🔍 情报中心 (Intelligence Center)                           │
│  ├── 全文检索（Elasticsearch 驱动）                           │
│  ├── 高级筛选（时间/分类/级别/来源/地域/标签）                  │
│  ├── 情报详情查看（含 LLM 分析结果）                           │
│  ├── 知识图谱关联查看                                        │
│  ├── 事件主线浏览                                            │
│  └── 导出功能（CSV/PDF）                                     │
│                                                             │
│  📄 报告中心 (Report Center)                                 │
│  ├── 历史报告浏览（按类型/日期）                                │
│  ├── 在线阅读 + PDF 下载                                     │
│  ├── 报告推送状态查询                                         │
│  └── 手动触发报告重新生成                                     │
│                                                             │
│  ⚙️ 情报源管理                                               │
│  ├── 情报源增删改查                                          │
│  ├── 批量导入/导出                                           │
│  ├── 健康状态监控                                            │
│  ├── 采集日志查看                                            │
│  └── 采集频率和配额配置                                       │
│                                                             │
│  🔑 关键词管理                                               │
│  ├── 按分类管理关键词                                        │
│  ├── 增删改查 + 批量操作                                     │
│  ├── 关键词命中统计                                           │
│  └── 搜索配额监控                                            │
│                                                             │
│  🕸️ 知识图谱                                                │
│  ├── 可视化图谱浏览（Neo4j 驱动）                              │
│  ├── 实体关系搜索                                            │
│  ├── 攻击路径分析                                            │
│  └── 供应链关系图                                            │
│                                                             │
│  📈 反馈统计                                                 │
│  ├── 各期报告满意度统计                                       │
│  ├── 情报类别价值分析                                        │
│  ├── 误判案例列表                                            │
│  └── 优化建议汇总                                            │
│                                                             │
│  ⚙️ 系统设置                                                │
│  ├── 订阅者管理                                              │
│  ├── 推送组配置                                              │
│  ├── 评分模型配置                                            │
│  ├── 调度时间配置                                            │
│  ├── LLM 模型切换                                           │
│  ├── 企业资产清单维护                                        │
│  ├── 供应商名录维护                                          │
│  └── 系统日志                                                │
└─────────────────────────────────────────────────────────────┘
```

### 17.2 权限控制

| 角色 | 权限 |
|------|------|
| **管理员** | 全部功能 |
| **安全运营** | 情报中心（全部）、报告中心、知识图谱、反馈统计 |
| **安全管理** | 情报源管理、关键词管理、评分配置、订阅者管理 |
| **高管/只读** | 仪表盘、报告中心（只读） |

认证方式：对接企业 LDAP/AD，支持 SSO。

---

## 18. 反馈闭环与持续优化

### 18.1 反馈收集机制

```
┌─────────────────────────────────────────────────────────────┐
│                    反馈闭环系统                                │
│                                                             │
│  收集渠道：                                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  1. 企微/飞书卡片按钮 → "有价值 👍" / "无价值 👎"         │  │
│  │  2. 报告底部满意度评分 → 1-5 星                          │  │
│  │  3. Web 控制台情报详情页 → 评价 + 文字反馈                 │  │
│  │  4. 邮件回复 → 解析关键词                                 │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  数据存储：                                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  CREATE TABLE feedback (                              │  │
│  │    id              BIGINT PRIMARY KEY AUTO_INCREMENT,  │  │
│  │    intel_id        BIGINT COMMENT '情报 ID',           │  │
│  │    report_id       BIGINT COMMENT '报告 ID',           │  │
│  │    subscriber_id   INT NOT NULL,                      │  │
│  │    feedback_type   ENUM('useful','useless',            │  │
│  │                         'rating','comment'),          │  │
│  │    rating          TINYINT COMMENT '1-5 星',           │  │
│  │    comment         TEXT,                              │  │
│  │    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP │  │
│  │  );                                                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  优化迭代：                                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  每月汇总分析：                                         │  │
│  │  1. 计算各类别情报的"有价值"率                             │  │
│  │  2. 识别高价值类别和低价值类别                              │  │
│  │  3. 调整评分模型权重                                      │  │
│  │     - "有价值"率 > 80% 的类别 → 维度权重不变或微升          │  │
│  │     - "有价值"率 < 40% 的类别 → 分析原因，可能降权          │  │
│  │  4. 优化 LLM Prompt                                    │  │
│  │     - 收集"无价值"标记的情报，分析误判原因                   │  │
│  │     - 将误判案例加入 Prompt 的 few-shot 示例               │  │
│  │  5. 生成月度反馈分析报告                                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 18.2 Prompt 持续优化流程

```
反馈数据 → 月度汇总
    │
    ├─ "无价值"标记的情报 → 分析模式
    │   ├─ 分类错误 → 优化分类 Prompt
    │   ├─ 评分过高 → 调整评分维度权重/细则
    │   ├─ 点评质量差 → 优化点评 Prompt + 补充示例
    │   └─ 与企业无关 → 强化相关性判断规则
    │
    ├─ "有价值"标记的情报 → 提取成功模式
    │   ├─ 记录被认可的分析风格
    │   └─ 强化 Prompt 中的成功模式
    │
    └─ 满意度趋势分析
        ├─ 满意度上升 → 保持当前策略
        └─ 满意度下降 → 紧急分析原因，调整策略
```

### 18.3 A/B 测试机制（需求文档未提及，补充）

支持对 Prompt 版本进行 A/B 测试：

- 同一批情报分别用 Prompt-A 和 Prompt-B 处理
- 随机将一半订阅者分配到 A 组、一半到 B 组
- 收集两组的反馈数据
- 统计显著性后选择表现更好的 Prompt 版本

---

# 第四部分：数据架构

## 19. 数据模型设计

### 19.1 核心表结构

```sql
-- =========================================
-- 情报主表（核心）
-- =========================================
CREATE TABLE intelligence (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,

    -- 基本信息
    title           VARCHAR(500) NOT NULL,
    title_zh        VARCHAR(500) COMMENT '中文标题（翻译后）',
    content         MEDIUMTEXT NOT NULL COMMENT '正文内容',
    content_zh      MEDIUMTEXT COMMENT '中文正文（翻译后）',
    summary         TEXT COMMENT '摘要',
    summary_zh      TEXT COMMENT '中文摘要',
    url             VARCHAR(2000) NOT NULL,
    author          VARCHAR(200),
    language        ENUM('zh', 'en', 'other') DEFAULT 'en',

    -- 来源信息
    source_id       BIGINT NOT NULL,
    source_name     VARCHAR(200),

    -- 分类与标签
    primary_category   VARCHAR(50) COMMENT '一级分类',
    secondary_category VARCHAR(50) COMMENT '二级分类',
    tags            JSON COMMENT '标签列表',

    -- 评分与分级
    score_relevance    DECIMAL(3,1) COMMENT '企业相关性评分',
    score_severity     DECIMAL(3,1) COMMENT '威胁严重性评分',
    score_timeliness   DECIMAL(3,1) COMMENT '时效性评分',
    score_actionability DECIMAL(3,1) COMMENT '可操作性评分',
    score_quality      DECIMAL(3,1) COMMENT '信息质量评分',
    total_score        DECIMAL(4,2) COMMENT '加权总分',
    priority_level     ENUM('P0', 'P1', 'P2', 'P3') DEFAULT 'P2',

    -- 分发等级
    tlp_level       ENUM('RED', 'AMBER', 'GREEN', 'CLEAR') DEFAULT 'GREEN',

    -- LLM 分析结果
    llm_comment     TEXT COMMENT 'LLM 点评',
    llm_impact      TEXT COMMENT 'LLM 影响分析',
    llm_action      TEXT COMMENT 'LLM 建议行动',

    -- ATT&CK 映射
    mitre_tactics   JSON COMMENT 'ATT&CK 战术列表',
    mitre_techniques JSON COMMENT 'ATT&CK 技术列表',

    -- 事件关联
    event_id        VARCHAR(50) COMMENT '关联事件主线 ID',

    -- 漏洞相关（可选）
    cve_id          VARCHAR(20),
    cvss_score      DECIMAL(3,1),
    affected_products JSON,

    -- 处理状态
    processing_status ENUM('raw', 'preprocessed', 'analyzed', 'published', 'archived') DEFAULT 'raw',
    fingerprint     CHAR(64) COMMENT 'SHA256 指纹（用于精确去重）',

    -- 向量 ID（Milvus 中的 ID）
    vector_id       BIGINT COMMENT 'Milvus 向量 ID',

    -- 时间
    published_at    DATETIME NOT NULL COMMENT '原始发布时间',
    collected_at    DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '采集时间',
    analyzed_at     DATETIME COMMENT '分析完成时间',

    -- 索引
    INDEX idx_priority (priority_level),
    INDEX idx_category (primary_category, secondary_category),
    INDEX idx_published (published_at),
    INDEX idx_collected (collected_at),
    INDEX idx_status (processing_status),
    INDEX idx_source (source_id),
    INDEX idx_event (event_id),
    INDEX idx_cve (cve_id),
    INDEX idx_fingerprint (fingerprint),
    INDEX idx_total_score (total_score DESC),
    FULLTEXT INDEX ft_title_content (title, title_zh, content, content_zh)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================
-- 事件主线表
-- =========================================
CREATE TABLE security_events (
    id              VARCHAR(50) PRIMARY KEY COMMENT 'evt-uuid',
    title           VARCHAR(500) NOT NULL COMMENT '事件标题',
    title_zh        VARCHAR(500),
    summary         TEXT COMMENT '当前最新状态综述',

    status          ENUM('developing', 'cooling_down', 'resolved', 'archived') DEFAULT 'developing',
    heat_score      INT DEFAULT 50 COMMENT '事件热度 0-100',

    first_seen      DATETIME NOT NULL,
    last_updated    DATETIME NOT NULL,

    timeline        JSON COMMENT '事件时间轴',
    affected_entities JSON COMMENT '受影响实体',
    mitre_techniques JSON COMMENT '关联 ATT&CK 技术',
    related_intel_count INT DEFAULT 1 COMMENT '关联情报数量',

    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_status (status),
    INDEX idx_heat (heat_score DESC),
    INDEX idx_last_updated (last_updated)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================
-- 报告表
-- =========================================
CREATE TABLE reports (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    report_type     ENUM('daily', 'weekly', 'monthly', 'quarterly',
                         'semi_annual', 'annual', 'emergency') NOT NULL,
    report_version  ENUM('executive', 'operational') NOT NULL,
    report_date     DATE NOT NULL COMMENT '报告日期',
    sequence_no     INT COMMENT '期号',

    title           VARCHAR(300) NOT NULL,
    content_html    MEDIUMTEXT COMMENT 'HTML 格式内容',
    content_json    JSON COMMENT '结构化数据',

    -- 安全态势
    threat_level    ENUM('critical', 'high', 'medium', 'low') COMMENT '态势等级',
    situation_summary TEXT COMMENT '态势总评',
    ai_insight      TEXT COMMENT 'AI 洞察',

    -- 统计
    intel_total     INT COMMENT '情报总量',
    intel_selected  INT COMMENT '入选情报数',
    p0_count        INT DEFAULT 0,
    p1_count        INT DEFAULT 0,

    -- 分发
    tlp_level       ENUM('RED', 'AMBER', 'GREEN', 'CLEAR') DEFAULT 'GREEN',

    -- 文件
    pdf_path        VARCHAR(500) COMMENT 'MinIO PDF 路径',

    -- 状态
    status          ENUM('generating', 'generated', 'pushing', 'pushed', 'failed') DEFAULT 'generating',
    generated_at    DATETIME,
    pushed_at       DATETIME,

    -- 覆盖时间范围
    period_start    DATETIME NOT NULL,
    period_end      DATETIME NOT NULL,

    INDEX idx_type_date (report_type, report_date),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================
-- 推送记录表
-- =========================================
CREATE TABLE push_log (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    report_id       BIGINT,
    intel_id        BIGINT COMMENT '单条紧急情报推送时',
    push_type       ENUM('report', 'emergency') NOT NULL,

    channel         ENUM('wechat_work', 'feishu', 'email', 'sms') NOT NULL,
    target_type     ENUM('individual', 'group') NOT NULL,
    target_id       VARCHAR(200) NOT NULL,

    status          ENUM('pending', 'sent', 'delivered', 'failed') DEFAULT 'pending',
    error_message   TEXT,
    retry_count     INT DEFAULT 0,

    sent_at         DATETIME,
    delivered_at    DATETIME,

    INDEX idx_report (report_id),
    INDEX idx_status (status),
    INDEX idx_sent_at (sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 19.2 数据关系图 (ER Diagram)

```
intel_sources ──1:N──→ intelligence
                            │
                            ├──N:1──→ security_events
                            │
                            ├──1:N──→ feedback
                            │
                            └──N:M──→ mitre_attack (通过 JSON 字段)

intelligence ──N:M──→ reports (通过 report_intel_map 表)

reports ──1:N──→ push_log

subscribers ──N:M──→ push_groups (通过 push_group_members)

subscribers ──1:N──→ feedback

search_keywords (独立维护)

enterprise_assets (独立维护，用于 CPE 匹配)

supply_chain_vendors (独立维护，用于供应链匹配)

scoring_config / scoring_overrides (独立维护)
```

---

## 20. 向量数据库设计

### 20.1 Milvus Collection 设计

```python
# Milvus Collection Schema
intel_vectors = Collection(
    name="intel_vectors",
    schema=CollectionSchema(
        fields=[
            FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema("intel_id", DataType.INT64),  # 关联 MySQL intelligence.id
            FieldSchema("title", DataType.VARCHAR, max_length=500),
            FieldSchema("published_date", DataType.VARCHAR, max_length=10),  # YYYY-MM-DD
            FieldSchema("category", DataType.VARCHAR, max_length=50),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=1024),  # bge-large-zh-v1.5
        ],
        description="Security intelligence embeddings for semantic dedup and search"
    )
)

# 创建索引
intel_vectors.create_index(
    field_name="embedding",
    index_params={
        "index_type": "IVF_FLAT",  # 精度优先
        "metric_type": "COSINE",
        "params": {"nlist": 1024}
    }
)
```

### 20.2 向量化策略

- **向量化内容：** `title_zh + summary_zh`（中文统一后的标题和摘要拼接）
- **向量模型：** bge-large-zh-v1.5（1024 维）
- **语义去重阈值：** Cosine Similarity ≥ 0.85 判定为重复
- **跨日去重阈值：** Cosine Similarity ≥ 0.80 判定为已推送过的内容
- **语义搜索：** 支持自然语言查询历史情报

### 20.3 向量数据生命周期

| 数据范围 | 存储位置 | 保留策略 |
|---------|---------|---------|
| 近 7 天 | Milvus 热数据 | 用于跨日去重 |
| 近 90 天 | Milvus 温数据 | 用于事件关联和语义搜索 |
| 90 天 - 2 年 | Milvus 冷数据（可选持久化到 S3） | 用于趋势分析 |
| 超过 2 年 | 归档删除向量，保留 MySQL 结构化数据 | 降低存储成本 |

---

## 21. 数据生命周期管理

### 21.1 数据保留策略

| 数据类型 | 保留周期 | 归档策略 | 删除策略 |
|---------|---------|---------|---------|
| 原始情报 | 2 年 | 2 年后转冷存储 | 3 年后可删除 |
| 分析结果 | 2 年 | 与原始情报同步 | 与原始情报同步 |
| 报告 | 永久 | PDF 归档至 MinIO | 不删除 |
| 推送日志 | 1 年 | 1 年后归档 | 2 年后删除 |
| 反馈数据 | 2 年 | 统计汇总后可归档 | 2 年后删除明细 |
| 审计日志 | 3 年 | 按合规要求 | 3 年后删除 |
| 向量数据 | 90 天（热）/ 2 年（冷） | 超期归档 | 与原始情报同步 |
| 知识图谱 | 永久 | 不归档 | 不删除（持续积累） |

### 21.2 自动清理任务

```yaml
# K8s CronJob - 数据清理
apiVersion: batch/v1
kind: CronJob
metadata:
  name: sia-data-cleanup
  namespace: sia-system
spec:
  schedule: "0 3 1 * *"  # 每月 1 日 03:00
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: cleanup
            image: sia-system/data-cleanup:latest
            env:
            - name: RETENTION_DAYS_INTEL
              value: "730"  # 2 年
            - name: RETENTION_DAYS_PUSH_LOG
              value: "365"  # 1 年
            - name: RETENTION_DAYS_VECTOR_HOT
              value: "90"   # 90 天
```

---

# 第五部分：安全与合规

## 22. 系统自身安全设计

### 22.1 凭证管理

**所有 API 密钥和敏感配置通过 K8s Secrets 管理：**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: sia-secrets
  namespace: sia-system
type: Opaque
data:
  deepseek-api-key: <base64-encoded>
  qwen-api-key: <base64-encoded>
  wechat-work-bot-key: <base64-encoded>
  feishu-bot-secret: <base64-encoded>
  mysql-password: <base64-encoded>
  redis-password: <base64-encoded>
  milvus-token: <base64-encoded>
  smtp-password: <base64-encoded>
  sms-api-key: <base64-encoded>
```

**凭证管理规范：**
- 所有 Secret 引用方式：`k8s-secret://sia-secrets/<key-name>`
- 禁止在代码、配置文件、日志中出现明文凭证
- 密钥轮换周期：每 90 天
- Pod 通过 ServiceAccount 和 RBAC 限制可访问的 Secret 范围
- 可选：集成 HashiCorp Vault 进行高级密钥管理

### 22.2 网络安全

```yaml
# K8s NetworkPolicy - 数据层仅允许来自应用层的流量
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sia-data-ingress
  namespace: sia-data
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: sia-system
    - namespaceSelector:
        matchLabels:
          name: dify
```

**其他网络安全措施：**
- 外部采集流量必须经企业正向代理出站
- Web 控制台通过 Ingress + TLS 暴露，HTTPS only
- 内部服务间通信使用 K8s Service DNS，不暴露外部端口
- 可选：启用 mTLS（Service Mesh）

### 22.3 应用安全

| 安全措施 | 实现方式 |
|---------|---------|
| 认证 | LDAP/AD SSO 对接 |
| 授权 | RBAC 角色权限控制 |
| 输入验证 | 所有 API 入口参数校验 |
| SQL 注入防护 | ORM 参数化查询 |
| XSS 防护 | 输出编码 + CSP 头 |
| CSRF 防护 | Token 验证 |
| 日志审计 | 所有关键操作记录审计日志 |
| 依赖安全 | 定期扫描 Python/npm 依赖漏洞 |

### 22.4 数据安全

- **传输加密：** 所有内部通信 TLS 1.2+
- **存储加密：** MySQL 开启 TDE（可选），MinIO 开启 SSE
- **备份加密：** 数据库备份文件 AES-256 加密
- **脱敏规则：** 情报中的个人信息（姓名、身份证号、手机号等）自动脱敏后存储和推送
- **数据分类：** 按 TLP 分类管理情报数据

---

## 23. 数据合规

### 23.1 合规要求矩阵

| 法规 | 适用场景 | SIA 合规措施 |
|------|---------|-------------|
| **GDPR** | 情报中涉及 EU 个人数据 | 个人信息脱敏；数据最小化；保留期限控制 |
| **个人信息保护法** | 情报中涉及中国公民数据 | 个人信息脱敏；不跨境传输原始个人数据 |
| **网络安全法** | 系统自身安全保障 | 等保合规；日志留存 ≥ 6 个月 |
| **数据安全法** | 企业数据处理 | 数据分类分级；重要数据保护 |

### 23.2 个人信息脱敏规则

当情报内容中包含个人信息时，自动应用以下脱敏规则：

| 信息类型 | 脱敏方式 | 示例 |
|---------|---------|------|
| 姓名 | 保留姓，名用 * 代替 | 张三 → 张** |
| 身份证号 | 保留前 3 位和后 4 位 | 110... → 110***********1234 |
| 手机号 | 保留前 3 位和后 4 位 | 13812345678 → 138****5678 |
| 邮箱 | 保留首字母和域名 | john@example.com → j***@example.com |
| IP 地址 | 保留前两段 | 192.168.1.100 → 192.168.*.* |
| 银行卡号 | 保留后 4 位 | **** **** **** 1234 |

脱敏处理在 LLM 分析之后、入库和推送之前执行。

---

## 24. 威胁建模（系统自身）

### 24.1 STRIDE 威胁分析

| 威胁类型 | 风险场景 | 缓解措施 |
|---------|---------|---------|
| **Spoofing** | 攻击者伪造情报源注入虚假情报 | 情报源白名单 + TLS 证书验证 + 来源可信度评分 |
| **Tampering** | 中间人篡改采集的情报内容 | HTTPS 采集 + 内容完整性校验 |
| **Repudiation** | 否认推送了某条情报 | 全链路审计日志 + 推送记录不可删改 |
| **Information Disclosure** | 敏感情报泄露给未授权人员 | TLP 分发等级 + RBAC 权限控制 |
| **Denial of Service** | 大量恶意请求导致系统不可用 | K8s 资源限制 + 速率控制 + HPA 自动扩缩 |
| **Elevation of Privilege** | 普通用户获取管理员权限 | RBAC + 最小权限原则 + 操作审计 |

### 24.2 供应链风险（系统自身）

| 风险 | 说明 | 缓解 |
|------|------|------|
| LLM 模型被投毒 | 私有部署的 LLM 模型被篡改 | 模型文件哈希校验 + 从官方源下载 |
| Python 依赖漏洞 | 第三方包存在安全漏洞 | Dependabot/Safety 定期扫描 + 锁定版本 |
| 容器镜像漏洞 | 基础镜像存在已知漏洞 | Trivy 镜像扫描 + 最小化基础镜像 |
| Dify 平台漏洞 | Dify 自身的安全漏洞 | 及时更新 + 网络隔离 |

### 24.3 LLM 特有风险（需求文档未提及，补充）

| 风险 | 说明 | 缓解 |
|------|------|------|
| **Prompt 注入** | 恶意情报内容中嵌入 Prompt 注入攻击，操纵 LLM 输出 | 输入清洗 + 结构化输出验证 + Prompt 与数据严格分离 |
| **幻觉/虚构** | LLM 虚构不存在的 CVE 或事件 | 关键信息（CVE、URL）二次验证 + 标注可信度 |
| **敏感信息泄露** | LLM 在分析中无意泄露训练数据中的敏感信息 | 使用私有化模型 + 输出过滤 |
| **一致性问题** | 同一情报多次分析结果不一致 | 固定 temperature + 结果缓存 + 关键输出人工抽检 |

---

# 第六部分：运维与保障

## 25. 监控与可观测性

### 25.1 监控指标体系

#### 业务指标（Grafana Dashboard: SIA-Business）

| 指标 | 查询 | 告警阈值 |
|------|------|---------|
| 每日情报采集量 | `sum(sia_collected_total{date=today})` | < 100 条/天 告警 |
| 去重后有效情报量 | `sum(sia_unique_total{date=today})` | < 50 条/天 告警 |
| P0/P1 检出量 | `sum(sia_priority_total{level=~"P0\|P1"})` | P0 > 5 条/天 告警（异常） |
| 日报推送准时率 | `sia_report_push_time - 08:00` | 延迟 > 30 分钟告警 |
| 情报源健康率 | `sia_source_healthy / sia_source_total` | < 90% 告警 |
| 反馈满意度 | `sia_feedback_positive / sia_feedback_total` | < 60% 告警 |

#### 系统指标（Grafana Dashboard: SIA-System）

| 指标 | 查询 | 告警阈值 |
|------|------|---------|
| LLM API 延迟 | `histogram_quantile(0.99, sia_llm_latency)` | P99 > 30s 告警 |
| LLM API 错误率 | `rate(sia_llm_errors) / rate(sia_llm_total)` | > 5% 告警 |
| LLM Token 消耗 | `sum(sia_llm_tokens_total)` | > 日配额 80% 告警 |
| 采集器错误率 | `rate(sia_collector_errors)` | > 10% 告警 |
| 数据库连接数 | `sia_db_connections` | > 80% 池上限告警 |
| Redis 内存使用 | `sia_redis_memory_used` | > 80% 告警 |
| Milvus 查询延迟 | `sia_milvus_query_latency_p99` | > 500ms 告警 |
| Pod 重启次数 | `kube_pod_container_status_restarts_total` | > 3 次/小时告警 |

#### 基础设施指标（Grafana Dashboard: SIA-Infra）

| 指标 | 说明 |
|------|------|
| CPU/内存/磁盘使用率 | 各 Pod 资源使用 |
| PV 存储使用率 | MySQL/ES/Milvus/MinIO 存储 |
| 网络 I/O | 入站/出站流量 |
| K8s 事件 | Pod 调度失败、OOM 等 |

### 25.2 日志规范

```json
{
    "timestamp": "2026-03-28T10:30:00.123Z",
    "level": "INFO",
    "service": "sia-collect",
    "module": "rss_collector",
    "trace_id": "abc-123-def",
    "message": "RSS feed collected successfully",
    "context": {
        "source_id": 42,
        "source_name": "The Hacker News",
        "items_count": 15,
        "duration_ms": 2340
    }
}
```

**日志级别使用规范：**
- ERROR：需要人工介入的错误
- WARN：可自动恢复的异常
- INFO：关键业务操作
- DEBUG：调试信息（生产环境默认关闭）

### 25.3 告警路由

```yaml
# Alertmanager 路由配置
route:
  receiver: default
  routes:
    - match:
        severity: critical
      receiver: oncall-sms
      continue: true
    - match:
        severity: critical
      receiver: oncall-wechat
    - match:
        severity: warning
      receiver: ops-wechat
    - match:
        severity: info
      receiver: ops-email

receivers:
  - name: oncall-sms
    # 短信通知值班人员
  - name: oncall-wechat
    # 企微通知值班群
  - name: ops-wechat
    # 企微通知运维群
  - name: ops-email
    # 邮件通知
```

---

## 26. 容错与灾备

### 26.1 单组件故障容错

| 组件 | 故障场景 | 容错策略 | 降级方案 |
|------|---------|---------|---------|
| **LLM 服务** | 主模型不可用 | 自动切换备用模型 | 仅推送原始标题+摘要，标注"未经 AI 分析" |
| **MySQL** | 主库不可用 | 自动切换到从库（只读） | 采集继续但暂停写入，数据暂存 Redis |
| **Milvus** | 服务不可用 | 跳过语义去重步骤 | 仅使用指纹精确去重 |
| **Redis** | 服务不可用 | 内存队列临时替代 | 降低吞吐量但不中断 |
| **Elasticsearch** | 服务不可用 | Web 搜索功能降级 | 搜索功能暂时不可用，其他功能正常 |
| **Neo4j** | 服务不可用 | 跳过知识图谱更新 | 不影响核心流程 |
| **企微/飞书 API** | API 不可用 | 重试 3 次后走邮件渠道 | 邮件兜底 |
| **邮件服务** | SMTP 不可用 | 重试 3 次后排队等待 | 延迟推送 |
| **采集器** | 单个源不可用 | 记录错误，下次重试 | 不影响其他源的采集 |

### 26.2 LLM API 容错详细设计

```
LLM 调用请求
    │
    ▼
┌──────────────────┐
│ 1. 检查缓存       │ ── 命中 → 返回缓存结果
│    (Redis)       │
└────────┬─────────┘
         │ 未命中
         ▼
┌──────────────────┐
│ 2. 调用主模型     │ ── 成功 → 写入缓存 → 返回
│    (DeepSeek)    │
└────────┬─────────┘
         │ 失败
         ▼
┌──────────────────┐
│ 3. 指数退避重试   │ ── 第 1 次：2s 后重试
│    (最多 3 次)    │    第 2 次：4s 后重试
│                  │    第 3 次：8s 后重试
└────────┬─────────┘
         │ 3 次都失败
         ▼
┌──────────────────┐
│ 4. 切换备用模型   │ ── 成功 → 返回（标注模型来源）
│    (Qwen 等)     │
└────────┬─────────┘
         │ 也失败
         ▼
┌──────────────────┐
│ 5. 降级方案       │
│  - 分类：规则引擎  │
│  - 评分：基础规则  │
│  - 点评：跳过      │
│  - 报告：标注     │
│    "未经AI分析"   │
└──────────────────┘
         │
         ▼
    触发运维告警
```

### 26.3 数据备份策略

| 数据源 | 备份方式 | 频率 | 保留 | 恢复 RTO |
|--------|---------|------|------|---------|
| MySQL | mysqldump + binlog | 每日全量 + 实时增量 | 30 天 | < 1 小时 |
| Milvus | Milvus backup API | 每周全量 | 4 周 | < 2 小时 |
| MinIO | 跨节点复制 | 实时 | 与数据同步 | < 30 分钟 |
| Neo4j | neo4j-admin dump | 每周全量 | 4 周 | < 1 小时 |
| ES | Snapshot API | 每日 | 7 天 | < 2 小时 |
| Redis | RDB + AOF | 实时 | 内存数据可丢失 | < 5 分钟 |

---

## 27. 性能与容量规划

### 27.1 资源需求估算

| 组件 | CPU (cores) | 内存 (GB) | 存储 (GB) | 副本数 |
|------|------------|-----------|-----------|--------|
| sia-api | 2 | 4 | - | 2 |
| sia-web | 0.5 | 1 | - | 2 |
| sia-collect | 2 | 4 | - | 2 |
| sia-analyze | 4 | 8 | - | 2 |
| sia-report | 2 | 4 | - | 1 |
| sia-emergency | 1 | 2 | - | 2 |
| sia-push | 1 | 2 | - | 1 |
| sia-gateway | 1 | 2 | - | 2 |
| MySQL | 4 | 16 | 200 (SSD) | 1+1 |
| Milvus | 4 | 16 | 100 (SSD) | 1 |
| Redis | 1 | 4 | - | 3 (Sentinel) |
| Elasticsearch | 4×3 | 8×3 | 300 (SSD) | 3 |
| Neo4j | 2 | 8 | 50 (SSD) | 1 |
| MinIO | 1×4 | 2×4 | 500 (HDD) | 4 |
| **总计** | **~45** | **~115** | **~1150** | |

### 27.2 LLM 资源需求（独立核算）

| 模型 | GPU | 显存 | 说明 |
|------|-----|------|------|
| DeepSeek-V3 (主) | A100 × 4（或等价） | 320 GB | 推理服务 |
| Qwen2.5 (备) | A100 × 2（或等价） | 160 GB | 备用推理 |
| bge-large-zh-v1.5 | T4 × 1 | 16 GB | 向量化服务 |

> 注：LLM 推理资源为企业已有部署，此处仅列出 SIA 系统所需的推理算力份额。

### 27.3 性能基准要求

| 指标 | 目标值 |
|------|-------|
| 日报生成端到端耗时 | ≤ 2 小时（04:00-06:00） |
| 单条情报预处理耗时 | ≤ 30 秒 |
| 单条情报 LLM 分析耗时 | ≤ 60 秒 |
| 语义去重查询延迟 | ≤ 200 ms |
| Web 控制台页面加载 | ≤ 2 秒 |
| 全文搜索响应 | ≤ 1 秒 |
| P0 情报从检出到推送 | ≤ 15 分钟 |
| API 响应时间 (P99) | ≤ 500 ms |

---

# 第七部分：实施规划

## 28. 分阶段上线计划

### Phase 1: MVP（最小可行产品）— 第 1-6 周

**目标：** 跑通核心流程，日报可用

| 周次 | 任务 | 交付物 |
|------|------|-------|
| W1-W2 | 基础设施搭建 | K8s Namespace、MySQL、Redis、MinIO 部署完成 |
| W2-W3 | RSS 采集器 + 情报预处理 | 50+ RSS 源接入，基础清洗和翻译 |
| W3-W4 | LLM 分析管线（分类+评分+点评） | Dify Workflow 编排完成 |
| W4-W5 | 日报生成 + 企微推送 | 日报模板 + 企微 Webhook 推送 |
| W5-W6 | 基础 Web 管理页面 | 情报源管理 + 情报列表浏览 |

**Phase 1 交付标准：**
- [x] 每日自动采集 50+ RSS 源
- [x] LLM 自动分类、评分、点评
- [x] 日报（高管版+运营版）每日 08:00 通过企微推送
- [x] 基础 Web 页面可查看情报和管理情报源

### Phase 2: 增强功能 — 第 7-12 周

**目标：** 完善情报源、去重、周报/月报、飞书/邮件推送

| 周次 | 任务 | 交付物 |
|------|------|-------|
| W7-W8 | 网页爬虫 + 微信公众号采集 | 100+ 情报源接入 |
| W8-W9 | Milvus 部署 + 语义去重 | 三级去重机制上线 |
| W9-W10 | 紧急情报检测 (P0/P1) | 即时推送通道上线 |
| W10-W11 | 周报/月报生成 | 周报+月报模板和 Workflow |
| W11-W12 | 飞书推送 + 邮件推送 + 短信 | 多渠道分发上线 |

**Phase 2 交付标准：**
- [x] 100+ 情报源全面覆盖
- [x] 语义去重准确率 ≥ 90%
- [x] P0/P1 紧急情报 ≤ 15 分钟推送
- [x] 周报/月报按时生成
- [x] 企微 + 飞书 + 邮件全渠道推送

### Phase 3: 高级智能 — 第 13-20 周

**目标：** 知识图谱、ATT&CK 映射、事件追踪、半年报/年报

| 周次 | 任务 | 交付物 |
|------|------|-------|
| W13-W14 | 事件追踪聚合引擎 | 事件主线追踪上线 |
| W14-W15 | NVD/CNVD 漏洞库对接 + 企业资产匹配 | 漏洞关联分析上线 |
| W15-W17 | Neo4j 知识图谱 + 实体提取 | 知识图谱基础功能 |
| W17-W18 | ATT&CK 映射 | ATT&CK 自动映射和热力图 |
| W18-W19 | 半年报/年报生成 | 长周期报告 |
| W19-W20 | 法规变化检测模块 | 全球法规监控上线 |

### Phase 4: 生态完善 — 第 21-28 周

**目标：** 反馈闭环、暗网监控、Web 控制台完善、性能优化

| 周次 | 任务 | 交付物 |
|------|------|-------|
| W21-W22 | 反馈闭环系统 | 交互式反馈收集 + 月度分析 |
| W22-W23 | Web 控制台完善（仪表盘、搜索、图谱可视化） | 完整 Web 控制台 |
| W23-W24 | 暗网监控 + 社交媒体监控 | 200+ 情报源全覆盖 |
| W24-W25 | 供应链安全监控模块 | 供应商名录匹配 |
| W25-W26 | A/B 测试 + Prompt 优化框架 | 持续优化机制 |
| W26-W28 | 性能调优 + 压力测试 + 文档完善 | 生产就绪 |

### 项目里程碑总览

```
W1          W6          W12         W20         W28
│           │           │           │           │
├───Phase 1──├───Phase 2──├───Phase 3──├───Phase 4──┤
│   MVP     │   增强     │   高级智能  │   生态完善  │
│           │           │           │           │
│  ✓ 日报   │  ✓ 去重   │  ✓ 知识图谱 │  ✓ 反馈闭环│
│  ✓ RSS    │  ✓ P0/P1  │  ✓ ATT&CK  │  ✓ 暗网监控│
│  ✓ 企微   │  ✓ 周/月报 │  ✓ 事件追踪 │  ✓ 完整UI │
│  ✓ 基础UI │  ✓ 多渠道  │  ✓ 法规监控 │  ✓ 性能优化│
```

---

## 29. 测试策略

### 29.1 测试层级

| 层级 | 范围 | 工具 | 执行频率 |
|------|------|------|---------|
| **单元测试** | 各模块核心逻辑 | pytest | 每次提交 |
| **集成测试** | 组件间交互 | pytest + testcontainers | 每日 CI |
| **端到端测试** | 完整采集→分析→推送流程 | 自定义测试框架 | 每周 |
| **LLM 输出质量测试** | 分类/评分/点评准确度 | 人工标注 + 自动评估 | 每周 |
| **性能测试** | 吞吐量/延迟/资源使用 | Locust + K6 | 每月 |
| **安全测试** | 漏洞扫描/渗透测试 | Trivy + OWASP ZAP | 每月 |

### 29.2 LLM 输出质量评估

```
评估方法：

1. 黄金标准数据集
   - 人工标注 200+ 条情报的分类、评分和点评
   - 作为 LLM 输出的评估基准

2. 自动评估指标
   - 分类准确率 (Accuracy): 目标 ≥ 85%
   - 评分一致性 (Spearman ρ): 目标 ≥ 0.80
   - 点评质量 (人工抽检满意度): 目标 ≥ 80%

3. 回归测试
   - 每次 Prompt 变更后，在黄金数据集上跑评估
   - 确保变更不导致质量下降

4. 对抗测试
   - 注入 Prompt 注入攻击样本，验证防护有效性
   - 注入无关内容，验证分类不会被误导
```

### 29.3 灾备演练

| 演练场景 | 频率 | 预期结果 |
|---------|------|---------|
| LLM 服务完全宕机 | 每季度 | 降级推送在 30 分钟内启动 |
| MySQL 主库故障 | 每季度 | 从库 5 分钟内自动接管 |
| 企微 API 不可用 | 每季度 | 邮件渠道 10 分钟内接管 |
| 完整流程 P0 紧急推送 | 每月 | 15 分钟内完成推送 |

---

## 30. 成本估算

### 30.1 基础设施成本（年度）

| 项目 | 规格 | 数量 | 估算（万元/年） |
|------|------|------|---------------|
| K8s Worker 节点 (SIA 专用) | 16C 64G | 4 台 | 硬件折旧 or 内部核算 |
| SSD 存储 | NVMe SSD | ~700 GB | 含在节点内 |
| HDD 存储 | SATA HDD | ~500 GB | 含在节点内 |
| GPU (LLM 推理份额) | A100 40G | 按份额 | 已有 LLM 集群分摊 |
| 网络带宽 | 出站代理 | 共享 | 企业已有 |

### 30.2 软件与服务成本

| 项目 | 说明 | 估算（万元/年） |
|------|------|---------------|
| WeRSS 订阅 | 微信公众号转 RSS | 1-3 |
| 短信服务 | P0 短信推送 | 0.5-1 |
| Dify 平台 | 企业版许可（如需） | 0-5 |
| 域名/证书 | 内部域名 | 0 |

### 30.3 人力成本

| 角色 | 职责 | 工作量 |
|------|------|-------|
| 后端开发 | 采集器、API、分析管线 | 2 人 × 7 个月 |
| 前端开发 | Web 控制台 | 1 人 × 4 个月 |
| Dify 编排 | Workflow 设计与调试 | 1 人 × 5 个月 |
| 安全分析师 | 情报源筛选、Prompt 调优、质量评估 | 1 人 × 7 个月（兼职） |
| 项目管理 | 项目协调与推进 | 1 人 × 7 个月（兼职） |
| **运维（上线后）** | 日常运维与监控 | 0.5 人常态化 |

---

## 31. 项目风险登记簿

| 编号 | 风险 | 可能性 | 影响 | 缓解措施 |
|------|------|-------|------|---------|
| R1 | LLM 分析质量不满足高管预期 | 中 | 高 | 充分 Prompt 工程 + 人工审核过渡期 + 反馈迭代 |
| R2 | 情报源不稳定导致采集覆盖不足 | 中 | 中 | 200+ 冗余情报源 + 健康监控 + 自动告警 |
| R3 | 去重算法误杀有价值情报 | 中 | 中 | 调高阈值宁可放过 + 人工抽检 + 阈值可调 |
| R4 | LLM 处理大量情报的吞吐量不足 | 低 | 高 | 批量处理 + 分级分析 + 异步并行 + 备用模型 |
| R5 | 企微/飞书 API 变更导致推送失败 | 低 | 中 | 适配层抽象 + 多渠道兜底 |
| R6 | 虚假情报被高分推送给高管 | 低 | 高 | 多源交叉验证 + 来源可信度权重 + 人工审核兜底 |
| R7 | 暗网监控触发法律风险 | 低 | 高 | 法务评审 + 仅只读监控 + 隔离容器 |
| R8 | 项目范围蔓延导致延期 | 中 | 中 | 严格分阶段交付 + 每阶段验收 |
| R9 | 关键人员离职导致知识断层 | 低 | 中 | 完善文档 + 低代码降低维护门槛 |
| R10 | Prompt 注入攻击操纵 LLM 输出 | 低 | 高 | 输入清洗 + 输出校验 + 结构化输出 + 安全测试 |

---

# 附录

## 附录 A：核心约束清单

1. 所有组件必须支持企业私有化部署，零公有云服务依赖。
2. 优先使用 Dify 低代码方案编排 Workflow，减少自定义代码维护成本。
3. 所有 AI 分析能力通过私有化 LLM 提供，默认 DeepSeek，可通过配置替换。
4. 情报价值评分规则为可编辑模块，以结构化 Prompt 形式固化在 Dify Workflow 中。
5. 情报源和搜索关键词持久化存储在数据库中，支持动态维护更新。
6. 全部凭证通过 K8s Secrets 管理，禁止明文存储。
7. 系统需具备完善的容错和降级能力，LLM 不可用时不影响基础情报推送。
8. 日报入选情报控制在 10 条以内，月报/半年报/年报控制在 20 条以内。
9. 情报数据合规，涉及个人信息时遵循 GDPR 及个人信息保护法要求。
10. 所有情报至少保留 2 年，报告永久保留。

## 附录 B：可编辑/可替换模块索引

| 模块 | 配置位置 | 说明 |
|------|---------|------|
| LLM 模型配置 | K8s ConfigMap + Dify | 可替换底层大模型（DeepSeek → Qwen 等） |
| 情报源管理 | MySQL + Web UI | 数据库持久化，支持增删改查 + 批量导入导出 |
| 搜索关键词库 | MySQL + Web UI | 按分类管理，支持动态更新 |
| 评分模型 | MySQL + Web UI | 维度/权重/细则均可独立调整 |
| 特殊规则覆写 | MySQL + Web UI | P0 强制规则可增删 |
| 情报筛选条数 | K8s ConfigMap | 日报≤10条，月报/半年报/年报≤20条 |
| 报告模板 | Jinja2 模板 + MinIO | 各类报告模板可独立修改 |
| 调度配置 | K8s CronJob + ConfigMap | 各报告推送时间可调整 |
| 推送目标 | MySQL + Web UI | 订阅者和推送组可动态管理 |
| 企业资产清单 | MySQL + Web UI | 用于漏洞关联匹配 |
| 供应商名录 | MySQL + Web UI | 用于供应链安全匹配 |
| LLM Prompt | Dify Workflow | 分类/评分/点评/总评等 Prompt 可独立编辑 |
| 脱敏规则 | ConfigMap | 个人信息脱敏正则规则 |
| 去重阈值 | ConfigMap | 语义去重/跨日去重的相似度阈值 |

## 附录 C：初始情报源清单（示例，非完整列表）

### 国际安全资讯 (RSS)

| 名称 | 类型 | 语言 | 优先级 |
|------|------|------|-------|
| The Hacker News | 安全资讯 | EN | 高 |
| BleepingComputer | 安全资讯 | EN | 高 |
| Dark Reading | 安全资讯 | EN | 高 |
| Krebs on Security | 安全博客 | EN | 高 |
| Schneier on Security | 安全博客 | EN | 中 |
| CISA Advisories | 政府公告 | EN | 高 |
| ENISA Publications | 政府公告 | EN | 高 |
| NVD Recent CVEs | 漏洞库 | EN | 高 |
| Google Project Zero | 研究团队 | EN | 高 |
| Microsoft Security Blog | 厂商公告 | EN | 高 |
| Auto-ISAC Alerts | 行业组织 | EN | 高 |

### 国内安全资讯 (RSS / WeRSS)

| 名称 | 类型 | 语言 | 优先级 |
|------|------|------|-------|
| FreeBuf | 安全资讯 | ZH | 高 |
| 安全客 | 安全资讯 | ZH | 高 |
| 先知社区 | 安全研究 | ZH | 中 |
| 奇安信威胁情报中心 | 威胁情报 | ZH | 高 |
| 腾讯安全威胁情报 | 威胁情报 | ZH | 高 |
| 国家信息安全漏洞共享平台 (CNVD) | 漏洞库 | ZH | 高 |
| 工信部网络安全管理局 | 政府公告 | ZH | 高 |
| 国家互联网信息办公室 | 政府公告 | ZH | 高 |
| 全国信息安全标准化技术委员会 | 标准 | ZH | 中 |

### 汽车行业专项

| 名称 | 类型 | 语言 | 优先级 |
|------|------|------|-------|
| Auto-ISAC | 行业组织 | EN | 高 |
| UNECE WP.29 | 法规标准 | EN | 高 |
| SAE International | 标准 | EN | 中 |
| Upstream Security | 车联网安全 | EN | 高 |
| Argus Cyber Security Blog | 车联网安全 | EN | 中 |

## 附录 D：关键词库初始配置

### 企业通用 IT 安全关键词

```
中文：数据泄露, 勒索软件, 0day漏洞, APT攻击, 供应链攻击, DDoS,
      钓鱼攻击, 安全漏洞通报, CVE高危漏洞, AD域控攻击, Exchange漏洞,
      VPN漏洞, 云平台安全, 终端安全, 邮件安全, 安全事件通报,
      勒索病毒, 挖矿木马, 安全补丁, 远程代码执行, 权限提升,
      信息泄露, SQL注入, 跨站脚本, 反序列化漏洞, 身份认证绕过

英文：data breach, ransomware, zero-day, APT, supply chain attack,
      DDoS, phishing, CVE, critical vulnerability, Active Directory,
      Exchange vulnerability, VPN exploit, cloud security, endpoint security,
      RCE, privilege escalation, SQL injection, XSS, authentication bypass
```

### 智能网联汽车行业关键词

```
中文：车联网漏洞, V2X安全, CAN总线攻击, ECU漏洞, 自动驾驶安全,
      OTA安全攻击, 智能座舱安全, 充电桩安全, UN R155, UN R156,
      ISO 21434, 汽车数据安全, 车主隐私泄露, Tier 1供应商安全事件,
      T-Box安全, TSP平台, 传感器欺骗, 高精地图数据安全, 固件篡改,
      车载以太网安全, UDS协议, DoIP安全, AUTOSAR安全

英文：connected car vulnerability, V2X security, CAN bus attack,
      ECU vulnerability, autonomous driving security, OTA security,
      EV charging security, vehicle data privacy, telematics security,
      sensor spoofing, firmware tampering, automotive cybersecurity
```

### 合规法规关键词

```
中文：GDPR执法, 个人信息保护法, 欧盟AI法案, 中国数据安全法,
      网络安全等级保护, 东南亚数据保护法规, 汽车数据安全管理,
      跨境数据传输, 数据出境安全评估, 关键信息基础设施,
      网络安全审查, 数据分类分级, 合规处罚, 监管执法

英文：GDPR enforcement, EU AI Act, data protection regulation,
      PDPA, cybersecurity law, data localization, cross-border data transfer,
      regulatory compliance, data classification, privacy regulation
```

## 附录 E：每日调度时间线

```
时间          任务                              触发方式
──────────────────────────────────────────────────────────────
00:00-04:00   情报采集                          K8s CronJob
              ├─ RSS 拉取 (每 4h)               WF-COLLECT-RSS
              ├─ 网页抓取 (每 12h)              WF-COLLECT-WEB
              ├─ API 采集 (每 6h)               WF-COLLECT-API
              └─ 法规检测 (每 24h)              WF-REGULATION

实时(24h)     紧急情报检测                      事件触发
              ├─ 新情报入库 → P0/P1 规则匹配     WF-EMERGENCY
              └─ 命中 → 即时分析 + 推送          WF-EMERGENCY-PUSH

04:00-06:00   AI 分析                          K8s CronJob
              ├─ 预处理 (清洗/翻译/NER/向量化)   WF-PREPROCESS
              ├─ 语义去重                        WF-DEDUP
              └─ LLM 深度分析 (分类/评分/点评)   WF-ANALYZE

05:00         情报源健康巡检                     WF-HEALTH

06:00-07:00   报告生成                          K8s CronJob
              ├─ 日报筛选 + LLM 撰写            WF-REPORT-DAILY
              └─ 模板渲染 + PDF 生成

08:00         日报推送                          WF-PUSH
              ├─ 企业微信推送
              ├─ 飞书推送
              └─ 邮件推送

周五 12:00    周报生成                          WF-REPORT-WEEKLY
周五 14:00    周报推送                          WF-PUSH

月末工作日    月报生成 + 推送                    WF-REPORT-MONTHLY
季末          季度报生成 + 推送                  WF-REPORT-QUARTERLY (可选)
7月初         半年报生成 + 推送                  WF-REPORT-SEMI
12月第3周     年报生成 + 推送                    WF-REPORT-ANNUAL
```

## 附录 F：数据依赖关系

```
日报   ← 当日原始情报
       ← LLM 分析结果
       ← 活跃事件主线

周报   ← 本周 5 份日报
       ← 全周原始情报
       ← LLM 周度洞察
       ← ATT&CK 周度统计

月报   ← 本月 4-5 份周报
       ← 全月原始情报
       ← 历史数据库（趋势对比）
       ← LLM 月度专项分析
       ← 知识图谱数据
       ← 反馈数据汇总

季度报 ← 3 份月报
       ← 全季度原始情报
       ← 历史数据库
       ← LLM 季度深度分析

半年报 ← 6 份月报 + 2 份季度报
       ← 全半年原始情报
       ← 历史数据库
       ← LLM 半年度战略分析
       ← 全球威胁格局分析

年报   ← 12 份月报 + 4 份季度报 + 半年报
       ← 全年原始情报
       ← 历史数据库
       ← LLM 年度综述 + 十大预测
       ← 全球威胁格局回顾与展望
```

## 附录 G：需求文档未涵盖的补充设计清单

以下为本方案超出原始需求文档的增量设计项：

| 编号 | 补充项 | 章节 | 价值说明 |
|------|-------|------|---------|
| S1 | **暗网监控** | 8.2.4 | 监控企业名称在暗网论坛中的出现，提前发现数据泄露或被攻击迹象 |
| S2 | **社交媒体监控** | 8.2.5 | Twitter/GitHub 上安全研究员经常率先披露 0day 和 PoC |
| S3 | **法规数据库采集器** | 8.2.6 | 将法规监控从隐含需求显式化为独立采集模块 |
| S4 | **知识图谱** | 12 | 建立安全实体关联，提升分析深度（供应链溯源、APT 画像等） |
| S5 | **MITRE ATT&CK 映射** | 13 | 标准化攻击分类，可对接 SOC 检测规则 |
| S6 | **企业资产清单匹配** | 15.3 | 自动判断漏洞是否影响企业使用的产品，精准 P0 判定 |
| S7 | **供应商名录匹配** | 15.4 | 自动识别供应链安全事件 |
| S8 | **TLP 分发等级** | 14.5 | 基于 TLP 协议的情报分发管控 |
| S9 | **LLM 统一适配层** | 5.2 | 模型故障转移、负载均衡、速率限制 |
| S10 | **LLM 特有风险防护** | 24.3 | Prompt 注入、幻觉、一致性等 LLM 特有安全风险 |
| S11 | **Web 控制台** | 17 | 完整的 Web 管理界面（仪表盘、搜索、图谱、管理） |
| S12 | **季度报** | 14.1 | 补充季度维度的报告，填充月报与半年报的空档 |
| S13 | **A/B 测试机制** | 18.3 | Prompt 版本科学对比，避免主观调优 |
| S14 | **威胁建模（系统自身）** | 24 | STRIDE 分析系统自身的安全风险 |
| S15 | **性能基准要求** | 27.3 | 明确可量化的性能目标 |
| S16 | **灾备演练计划** | 29.3 | 定期验证容错机制有效性 |
| S17 | **P3 低价值情报级别** | 11.1 | 增加 P3 级别用于过滤低价值信息，避免噪音 |
| S18 | **事件归档规则** | 10.2 | 明确事件主线的生命周期管理 |
| S19 | **采集高峰期策略** | 8.3 | 重大事件后自动提升采集频率 |
| S20 | **LLM 调用优化策略** | 9.3 | 批量处理、分级分析、缓存复用等降本增效措施 |

---

> **文档结束**
> 本方案涵盖了安全洞察与情报分析智能体的完整系统设计，从战略目标到技术细节，从核心功能到运维保障，从安全合规到实施规划。方案遵循"全私有化部署、低代码优先、模型可替换、渐进式增强"四大原则，确保系统既满足当前需求又具备持续演进能力。
