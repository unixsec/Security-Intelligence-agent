# SIA 文档索引

Security Intelligence Agent（SIA）v0.2.0 的全部工程文档。面向三类读者：

| 我是… | 先读 |
|---|---|
| **部署实施 / SRE** | [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) → [`CONFIGURATION.md`](./CONFIGURATION.md) → [`OPERATIONS_GUIDE.md`](./OPERATIONS_GUIDE.md) |
| **开发 / 打包** | [`BUILD_GUIDE.md`](./BUILD_GUIDE.md)（架构详解见维护者本地 `design/`） |
| **终端用户 / 分析师** | [`USER_MANUAL.md`](./USER_MANUAL.md) |
| **安全审计** | [`SECURITY.md`](./SECURITY.md) |
| **API 集成方** | [`API_REFERENCE.md`](./API_REFERENCE.md) |

## 文档清单

### 工程与运维文档（本目录）

| 文档 | 内容 |
|---|---|
| [`BUILD_GUIDE.md`](./BUILD_GUIDE.md) | 从源码构建后端 / 前端 Docker 镜像 |
| [`DEPLOYMENT_GUIDE.md`](./DEPLOYMENT_GUIDE.md) | 企业 Kubernetes 一键部署（权威操作文档） |
| [`CONFIGURATION.md`](./CONFIGURATION.md) | 所有占位符 / 环境变量 / Helm 值的完整参考 |
| [`OPERATIONS_GUIDE.md`](./OPERATIONS_GUIDE.md) | 日常运维：扩缩容、滚动升级、回滚、备份、排障 |
| [`SECURITY.md`](./SECURITY.md) | 威胁模型、加固清单、应急响应 |
| [`USER_MANUAL.md`](./USER_MANUAL.md) | Web 控制台使用手册 |
| [`API_REFERENCE.md`](./API_REFERENCE.md) | REST API 参考与集成示例 |

### 设计文档（本地）

详细设计文档（架构、ER、序列、状态机、威胁模型、NFR、FMEA、多 region 拓扑、ADR 等）由维护者在本地仓库根的 `design/` 目录维护，**该目录由 `.gitignore` 整体排除，不会随 git 上传到 GitHub**，仅供本地分析与内部评审使用。

如果你是仓库维护者：直接在本地 `design/` 下浏览即可。如果你是外部贡献者：本仓库的公开技术信息以本目录（`docs/`）下的文档为准；对架构/安全模型有进一步问题请通过 `SECURITY.md` 中的渠道联系维护者。

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
