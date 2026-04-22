# SIA 文档索引

Security Intelligence Agent（SIA）v0.2.0 的全部工程文档。面向三类读者：

| 我是… | 先读 |
|---|---|
| **部署实施 / SRE** | [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) → [`CONFIGURATION.md`](./CONFIGURATION.md) → [`OPERATIONS_GUIDE.md`](./OPERATIONS_GUIDE.md) |
| **开发 / 打包** | [`ARCHITECTURE.md`](./ARCHITECTURE.md) → [`BUILD_GUIDE.md`](./BUILD_GUIDE.md) |
| **终端用户 / 分析师** | [`USER_MANUAL.md`](./USER_MANUAL.md) |
| **安全审计** | [`SECURITY.md`](./SECURITY.md) |
| **API 集成方** | [`API_REFERENCE.md`](./API_REFERENCE.md) |

## 文档清单

### 工程与运维文档（本目录）

| 文档 | 内容 |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | 系统架构、组件职责、数据流（简化概览） |
| [`BUILD_GUIDE.md`](./BUILD_GUIDE.md) | 从源码构建后端 / 前端 Docker 镜像 |
| [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) | 企业 Kubernetes 一键部署（权威操作文档） |
| [`CONFIGURATION.md`](./CONFIGURATION.md) | 所有占位符 / 环境变量 / Helm 值的完整参考 |
| [`OPERATIONS_GUIDE.md`](./OPERATIONS_GUIDE.md) | 日常运维：扩缩容、滚动升级、回滚、备份、排障 |
| [`SECURITY.md`](./SECURITY.md) | 威胁模型、加固清单、应急响应 |
| [`USER_MANUAL.md`](./USER_MANUAL.md) | Web 控制台使用手册 |
| [`API_REFERENCE.md`](./API_REFERENCE.md) | REST API 参考与集成示例 |

### 设计文档（`../design/`）

| 文档 | 内容 |
|---|---|
| [`../design/Security_Intelligence_Agent_Design_v5.0.md`](../design/Security_Intelligence_Agent_Design_v5.0.md) | **当前权威设计（v5.0）**：C4 架构图、序列图、状态机、ER、威胁 DFD、ADR、NFR、FMEA |

历史版本（v1.0 / v2.0 / v3.0 / v4.0 / Final）保留在 `design/` 目录下供溯源，不再作为实施依据。

## 快速开始（部署）

```bash
cp deploy/deployment.config.example.yaml deployment.config.yaml
$EDITOR deployment.config.yaml                        # 填占位符
./scripts/deploy/configure.sh --generate-secrets      # 生成 values-prod.yaml + Secret
./scripts/deploy/deploy-k8s.sh                        # 构建 + 推镜像 + helm + 冒烟
```

细节见 [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md)。

## 版本

- SIA：`v0.2.0`
- Helm Chart：`0.2.0`
- 文档日期：2026-04-22

> 本文档使用简体中文，代码示例与命令保持英文。
