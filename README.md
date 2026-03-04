# Security-Intelligence-agent
Security Intelligence agent
# 安全情报分析智能体 (Security Intelligence Agent)

> **版本**：v1.0  
> **作者**：alex (unix_sec@163.com)  
> **协议**：Apache 2.0（商业使用需获得作者授权，详见 LICENSE）  
> **更新日期**：2026-03-04

---

## 项目简介

安全情报分析智能体是一套**全自动化**的安全情报采集、分析、评分、报告生成和推送系统。

系统运行在企业 K8s 私有云上，以 **Dify** 低代码平台为核心编排引擎，以私有化部署的 **LLM（默认 DeepSeek）** 为 AI 分析核心，实现从原始情报到结构化报告的端到端处理。

### 核心能力

- **多源情报采集**：支持 RSS、网页抓取、360 搜索三类采集方式
- **AI 智能分析**：基于 LLM 的五维评分模型（威胁可能性、业务影响度、合规影响度、时效紧迫性、情报质量）
- **语义去重**：基于 Milvus 向量数据库，余弦相似度阈值 0.92，跨 7 天去重
- **多级情报**：P0（即时推送）/ P1（4h 内推送）/ P2（日报汇总）
- **多类报告**：日报、周报、月报、半年报、年报，每类均含高管简版和安全运营详版
- **多渠道推送**：企业微信、邮件、短信（P0 紧急）
- **反馈闭环**：读者评分反馈，自动触发评分模型调优
- **全私有化部署**：所有组件运行在企业 K8s 集群内，零公有云依赖

---

## 技术架构

| 层次 | 组件 | 技术选型 |
|------|------|---------|
| 编排引擎 | Dify | Dify Community Edition |
| AI 引擎 | LLM | DeepSeek（默认，可替换） |
| 向量引擎 | VectorDB | Milvus |
| 结构化存储 | 关系型数据库 | MySQL 8.0 |
| 缓存/队列 | 消息队列 | Redis |
| 采集器 | RSS | Feedparser (Python) |
| 采集器 | 网页 | Playwright / requests |
| 采集器 | 搜索 | 360 Search API |
| 推送 | 企业微信 | WeCom Bot API |
| 推送 | 邮件 | SMTP |
| 推送 | 短信 | 企业短信网关 API |
| 管理前端 | Web UI | Vue3 + ElementPlus |
| 监控 | 可观测性 | Prometheus + Grafana |

---

## 项目结构

```
Security_Intelligence_agent/
├── LICENSE                         # Apache 2.0 + 商业使用条款
├── README.md                       # 本文件
├── .gitignore
├── docs/
│   ├── design-spec.md              # 技术设计方案
│   ├── 01-编译手册.md               # 编译与构建指南
│   ├── 02-部署指南.md               # K8s 部署指南
│   ├── 03-操作手册.md               # 系统操作手册
│   └── 04-帮助文档.md               # 用户帮助文档
├── database/
│   ├── ddl.sql                     # 数据库建表语句
│   ├── seed.sql                    # 初始化数据
│   └── migrations/                 # 数据库变更迁移
├── collectors/                     # 情报采集器（Python）
│   ├── common/                     # 公共模块
│   ├── rss_collector/              # RSS 采集器
│   ├── web_collector/              # 网页采集器
│   ├── search_collector/           # 360 搜索采集器
│   ├── requirements.txt
│   └── helm/                       # 采集器 Helm Chart
├── admin-api/                      # 管理后台 API（FastAPI）
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routes/
│   │   ├── models/
│   │   └── services/
│   ├── requirements.txt
│   └── Dockerfile
├── admin-web/                      # 管理前端（Vue3 + ElementPlus）
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── dify-workflows/                 # Dify Workflow 定义文件
│   ├── wf-2-analysis-scoring.yml
│   ├── wf-3-dedup.yml
│   ├── wf-4-emergency.yml
│   ├── wf-5-daily-report.yml
│   ├── wf-6-weekly-report.yml
│   ├── wf-7-monthly-report.yml
│   ├── wf-8-periodic-report.yml
│   ├── wf-9-push.yml
│   ├── wf-10-feedback.yml
│   └── wf-11-health-check.yml
├── helm/                           # K8s Helm Chart（全量部署）
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
└── scripts/
    ├── setup.sh                    # 一键部署脚本
    ├── test-llm.py                 # LLM 能力验证
    └── migrate-scoring-model.py    # 评分模型升级脚本
```

---

## 快速开始

详细步骤请参阅以下文档：

| 文档 | 说明 |
|------|------|
| [编译手册](docs/01-编译手册.md) | 如何构建各组件的 Docker 镜像 |
| [部署指南](docs/02-部署指南.md) | 如何在 K8s 集群上完整部署本系统 |
| [操作手册](docs/03-操作手册.md) | 日常运维操作和管理界面使用 |
| [帮助文档](docs/04-帮助文档.md) | 功能介绍、FAQ 和故障排查 |

### 前置依赖

- Kubernetes 1.24+
- Helm 3.x
- Docker 20.x+
- MySQL 8.0（或 K8s StatefulSet）
- Milvus 2.x（或 K8s StatefulSet）
- Redis 7.x
- Dify Community Edition
- DeepSeek / 任何 OpenAI 兼容 LLM

### 5 分钟快速部署

```bash
# 1. 克隆项目
git clone <repo-url>
cd Security_Intelligence_agent

# 2. 配置凭证（编辑 values.yaml）
cp helm/values.yaml helm/values-local.yaml
vim helm/values-local.yaml

# 3. 执行一键部署
bash scripts/setup.sh

# 4. 验证 LLM 连接
python scripts/test-llm.py
```

---

## 开发分期

| 阶段 | 目标 | 周期 |
|------|------|------|
| 第一期 MVP | 日报端到端自动化 | 4-6 周 |
| 第二期 完善 | 全报告体系 + 紧急情报 + 管理界面 | 3-4 周 |
| 第三期 优化 | 反馈闭环 + 长周期报告 + 运维完善 | 2-3 周 |

---

## 许可证

本项目采用 **Apache License 2.0** 协议。  

> **重要提示**：如需将本项目用于**商业用途**，必须事先获得作者书面授权。  
> 商业授权联系：unix_sec@163.com

详见 [LICENSE](LICENSE) 文件。

---

## 作者

**alex**  
邮箱：unix_sec@163.com
