# 阿里云从零部署 SIA 指南

> **目标读者**：第一次接触阿里云、第一次接触 Kubernetes 的运维人员。
> **目标结果**：跟着这份文档一步步操作，能在阿里云上把 SIA 跑起来，并能从公网访问 Web 控制台。
>
> **不是为谁写的**：已经在生产环境深度使用 ACK / RDS 的资深 SRE。
>
> 文档版本：2026-04-30 ｜ 适用 SIA 版本：v0.4
> 阿里云控制台首页：[https://home.console.aliyun.com](https://home.console.aliyun.com)

---

## 0. 你将要创建什么

| # | 阿里云服务 | 名称 | 用途 |
|---|---|---|---|
| 1 | VPC 专有网络 | `sia-vpc` | 一个隔离的私有网络容纳全部资源 |
| 2 | 容器镜像服务 ACR | `sia-acr`（个人版即可） | 存放 sia-backend、sia-web 镜像 |
| 3 | 容器服务 ACK | `sia-ack` 托管版 | 跑 SIA 的 Kubernetes 集群 |
| 4 | 云数据库 RDS for MySQL 8.0 | `sia-mysql` | 业务数据库 |
| 5 | 云数据库 Tair（Redis 7） | `sia-redis` | 流 / 限速 / JWT 撤销 |
| 6 | 对象存储 OSS | `sia-reports-<随机>` | 报告 PDF / HTML 归档（替代自建 MinIO） |
| 7 | 域名 + ICP 备案 | `sia.your-domain.com` | 公网入口 |
| 8 | SSL 证书 | Let's Encrypt（cert-manager）或 阿里云免费 DV | HTTPS |

**预算估算（按需 / 按月，华东 1-杭州 region）**：

| 资源 | 规格 | 月费（约） |
|---|---|---|
| ACK 托管集群（标准版） | 集群管理费免费，仅付 ECS | 0 |
| ECS 节点 ×3 | 4 vCPU / 8 GiB（ecs.c6.xlarge） | ¥600–900（按量）/ ¥350（包年包月） |
| RDS MySQL 8.0 | 通用型 4 vCPU / 8 GiB / 100 GiB SSD | ¥600 起 |
| Redis Tair 标准版 | 4 GiB 主从 | ¥300 起 |
| OSS | 100 GiB + 公网下行 | ¥10–50 |
| ACR 个人版 | 免费 | 0 |
| SLB（ACK 自动创建） | 一台标准型 I | ¥30–50 |
| **小计** | | **¥1500–2000 / 月** |

**先决条件**：
- 阿里云账号已实名（个人 / 企业），账户余额 ≥ ¥200。
- 已购买并备案至少一个域名（中国大陆机房需 ICP 备案；如选**境外/香港 region**可跳过备案）。
- 本地工作机已安装 `git`、`docker`、`kubectl`、`helm`（参考下方"工具准备"）。

---

## 1. 准备工作

### 1.1 工具安装（本地工作机）

| 工具 | 最低版本 | 安装 |
|---|---|---|
| `git` | 任意 | [git-scm.com](https://git-scm.com) |
| `docker` | 24+ | [docker.com](https://www.docker.com/products/docker-desktop) |
| `kubectl` | 1.28+ | [kubernetes.io/docs/tasks/tools](https://kubernetes.io/docs/tasks/tools/) |
| `helm` | 3.12+ | [helm.sh/docs/intro/install](https://helm.sh/docs/intro/install/) |

Windows 用户推荐 WSL2 + Ubuntu 22.04 来运行后续 bash 命令。

```bash
# 验证安装
git --version
docker version
kubectl version --client
helm version
```

### 1.2 克隆 SIA 源码

```bash
git clone <SIA-REPO-URL> sia
cd sia
```

### 1.3 选择 Region

国内 / 中国大陆机房推荐 **cn-hangzhou**（华东 1，资源最全、价格优）。
不想做 ICP 备案 → 选 **cn-hongkong**（中国香港）。
本指南后续命令以 `cn-hangzhou` 为示例，如选其他 region 自行替换。

---

## 2. 网络底座：VPC + 交换机 + 安全组

### 2.1 创建 VPC

参考阿里云文档：<https://help.aliyun.com/zh/vpc/user-guide/create-and-manage-vswitch>

**控制台路径**：[VPC 控制台](https://vpc.console.aliyun.com) → 专有网络 → 创建专有网络

| 字段 | 推荐值 |
|---|---|
| 地域 | 华东 1（杭州） |
| 名称 | `sia-vpc` |
| IPv4 网段 | `10.0.0.0/16` |
| IPv6 | 不开启（首次部署简化） |

### 2.2 创建 vSwitch（交换机）

ACK 集群至少需要 **3 个不同可用区的交换机**保证 HA。在创建 VPC 的同一页面或之后：

| 名称 | 可用区 | IPv4 网段 |
|---|---|---|
| `sia-vsw-h` | 可用区 H | `10.0.1.0/24` |
| `sia-vsw-i` | 可用区 I | `10.0.2.0/24` |
| `sia-vsw-j` | 可用区 J | `10.0.3.0/24` |

> 不同 region 可用区代号不同，按控制台下拉框列出的实际选择。

### 2.3 创建安全组

**控制台路径**：[ECS 控制台](https://ecs.console.aliyun.com) → 网络与安全 → 安全组 → 创建

| 字段 | 推荐值 |
|---|---|
| 名称 | `sia-sg` |
| 网络类型 | 专有网络 |
| 专有网络 | 选刚创建的 `sia-vpc` |
| 安全组类型 | 普通安全组 |

**入方向规则**（暂留为默认；ACK 创建集群时会自动加规则）。

---

## 3. 容器镜像服务 ACR

参考：<https://help.aliyun.com/zh/acr/user-guide/create-a-container-registry-personal-edition-instance>

### 3.1 开通个人版

**控制台**：[ACR 控制台](https://cr.console.aliyun.com) → 实例列表 → 创建 → 个人版（免费）

首次开通需要设置一个 **Registry 登录密码**（与阿里云账号密码不同）。记下来；后面要用。

### 3.2 创建命名空间

进入个人版实例 → 左侧 **命名空间** → 创建命名空间：

| 字段 | 值 |
|---|---|
| 命名空间 | `sia` |
| 自动创建仓库 | 开 |
| 默认仓库类型 | 私有 |

镜像地址前缀（记下）：

```
registry.cn-hangzhou.aliyuncs.com/sia/<image-name>
```

### 3.3 本地登录 + 推送

```bash
# 1. 登录（用你刚才设置的 Registry 密码，不是阿里云账号密码）
docker login --username=<阿里云账号名> registry.cn-hangzhou.aliyuncs.com

# 2. 在 SIA 仓库根目录构建两个镜像
TAG=v0.4.0
REG=registry.cn-hangzhou.aliyuncs.com/sia

docker build -f deploy/docker/Dockerfile     -t $REG/sia-backend:$TAG .
docker build -f deploy/docker/Dockerfile.web -t $REG/sia-web:$TAG     .

# 3. 推送
docker push $REG/sia-backend:$TAG
docker push $REG/sia-web:$TAG
```

> 个人版每天有免费 pull / push 配额。生产推荐**企业版**（支持多 region 同步、镜像扫描、Cosign 签名）。

---

## 4. 数据库：RDS MySQL 8.0

参考：<https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/create-an-apsaradb-rds-for-mysql-instance-1>

### 4.1 创建实例

**控制台**：[RDS 控制台](https://rdsnext.console.aliyun.com) → 创建实例

| 字段 | 推荐值（试点） |
|---|---|
| 计费方式 | 包年包月（首次更便宜）/ 按量 |
| Region | 华东 1（杭州） |
| 数据库引擎 | MySQL **8.0** |
| 系列 | 高可用版 / 基础版（试点选基础版） |
| 存储类型 | ESSD 云盘（PL1） |
| 实例规格 | 通用型 `mysql.n2.medium.2c`（2 vCPU / 4 GiB）起，生产 ≥ 4C8G |
| 存储空间 | 100 GiB |
| 网络类型 | 专有网络 → 选 `sia-vpc` + 任一 vSwitch |
| 时区 | UTC（重要，与 SIA 默认一致） |
| 字符集 | utf8mb4 |
| 实例名 | `sia-mysql` |

### 4.2 创建账号与库

实例创建后：

1. **账号管理** → 创建账号：
   - 用户名：`sia`
   - 账号类型：高权限账号
   - 密码：生成强密码，保存到密码管理器（**24 位以上、含大小写数字符号**）
2. **数据库管理** → 创建数据库：
   - 库名：`sia`
   - 字符集：`utf8mb4`

### 4.3 白名单

**安全管理** → 白名单设置 → 修改默认白名单分组：

```
10.0.0.0/16    （即 VPC 网段，让 ACK 内网访问）
```

不要保留默认的 `127.0.0.1`（生产会过滤掉来自 ACK 的连接）。

### 4.4 记下连接信息

| 字段 | 示例 |
|---|---|
| 内网地址 | `rm-xxxxx.mysql.rds.aliyuncs.com` |
| 端口 | `3306` |
| 账号 | `sia` |
| 密码 | （刚才生成的） |
| 数据库 | `sia` |

---

## 5. Redis：云数据库 Tair（兼容 Redis 7）

参考：<https://help.aliyun.com/zh/redis/getting-started/step-1-create-an-apsaradb-for-redis-instance>

### 5.1 创建实例

**控制台**：[Tair 控制台](https://kvstorenext.console.aliyun.com) → 创建实例

| 字段 | 推荐值 |
|---|---|
| 计费方式 | 包年包月 |
| Region | 华东 1（杭州） |
| 引擎版本 | Redis 开源版 **7.0** |
| 架构 | 标准版（主从） |
| 实例规格 | 1 GiB 主从（试点）/ ≥ 4 GiB 主从（生产） |
| 网络类型 | 专有网络 → `sia-vpc` |
| vSwitch | 选其中一个 |
| 实例名 | `sia-redis` |

### 5.2 设置密码 + 白名单

1. 实例详情 → **账号管理** → 重置密码：保存到密码管理器。
2. **白名单设置** → 修改 default 白名单：填 `10.0.0.0/16`。
3. 记下：
   - 内网地址：`r-xxxxx.redis.rds.aliyuncs.com`
   - 端口：`6379`
   - 密码：刚才设置的

---

## 6. OSS 对象存储（替代 MinIO）

SIA 默认用 MinIO 归档报告。在阿里云直接用 OSS 更轻量（不用自己跑 MinIO）。

参考：<https://help.aliyun.com/zh/oss/user-guide/create-a-bucket-4>

### 6.1 创建 Bucket

**控制台**：[OSS 控制台](https://oss.console.aliyun.com) → Bucket 列表 → 创建 Bucket

| 字段 | 推荐值 |
|---|---|
| Bucket 名称 | `sia-reports-<6 位随机字母>`（全局唯一） |
| 地域 | 华东 1（杭州）—— **必须与 ACK 同 region** |
| 存储类型 | 标准存储 |
| 同城冗余 | 关闭（试点）/ 开启（生产 DR） |
| 读写权限 | **私有** |
| 服务端加密 | OSS 完全托管 |
| 版本控制 | 开启（防误删） |

### 6.2 创建 RAM 子账号 + AccessKey

不要用主账号 AccessKey！

**控制台**：[RAM 控制台](https://ram.console.aliyun.com) → 用户 → 创建用户

1. 用户名：`sia-oss`，访问方式：勾选 **OpenAPI 调用访问**
2. 创建后**立即下载 CSV**，含 AccessKey ID + Secret（仅这一次能下载）。
3. 给这个用户授权：添加权限 → `AliyunOSSFullAccess`（更严格的话用自定义策略只允许该 Bucket 读写）。

### 6.3 SIA 用 MinIO SDK 兼容 OSS

SIA 使用 `minio` Python SDK；OSS 提供 S3 兼容端点：

```
endpoint: oss-cn-hangzhou.aliyuncs.com
access_key: <AccessKey ID>
secret_key: <AccessKey Secret>
secure: true
bucket: sia-reports-xxxxxx
```

> 注意：OSS 的 S3 兼容路径与原生 OSS API 略有差异。如出现 SDK 报错，回退方案是在 K8s 集群里跑一个 MinIO Pod，详见 §10 备选方案。

---

## 7. 容器服务 ACK 托管集群

参考：<https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/getting-started/quick-start-for-first-time-users>

### 7.1 首次开通授权

第一次用 ACK 需要给阿里云授权（一次性）。控制台会自动引导。

### 7.2 创建集群

**控制台**：[ACK 控制台](https://cs.console.aliyun.com) → 集群 → 创建 Kubernetes 集群 → ACK 托管版

#### 集群配置

| 字段 | 推荐值 |
|---|---|
| 集群名称 | `sia-ack` |
| Region | 华东 1（杭州） |
| Kubernetes 版本 | 选最新稳定（≥ 1.28） |
| 容器运行时 | containerd |
| VPC | `sia-vpc` |
| Pod CIDR | `172.20.0.0/16` |
| Service CIDR | `172.21.0.0/20` |
| 公网 SLB | 创建（用于公网 API server 访问） |
| 安全组 | 自动创建 |
| 时区 | UTC |
| 集群本地 DNS | NodeLocal DNSCache 开启 |

#### 节点池配置

| 字段 | 推荐值 |
|---|---|
| 节点池名称 | `sia-default` |
| 计费类型 | 按量（试点）/ 包年包月（生产） |
| 实例规格 | `ecs.c6.xlarge`（4C8G）—— 至少满足 SIA `consumer + api` 共存 |
| 系统盘 | ESSD 云盘 PL1，60 GiB |
| 节点数 | 3（保证 HA） |
| 操作系统 | Alibaba Cloud Linux 3.2104 |
| 容器数据盘 | 100 GiB（用于镜像缓存） |
| 网络 | 三个 vSwitch 都选上 |

#### 组件配置

| 选项 | 选择 |
|---|---|
| 网络插件 | Terway（VPC 直通）或 Flannel（简单） |
| 服务发现 | CoreDNS |
| Ingress | nginx-ingress（**勾选**，自动创建 SLB） |
| 监控 | 安装 logtail + ARMS Prometheus（可选；试点跳过） |

点击 **创建集群**，等待 10-15 分钟。

### 7.3 配置本地 kubectl

集群创建完成后：**集群信息** → **连接信息** → 复制 **公网访问 kubeconfig** 内容到本地 `~/.kube/config`：

```bash
mkdir -p ~/.kube
# 把控制台复制的 yaml 粘贴保存
vim ~/.kube/config

# 验证
kubectl get nodes
# 应看到 3 个 Ready 节点
```

### 7.4 创建 namespace + 镜像拉取 Secret

```bash
kubectl create namespace sia

# 让 K8s 能从 ACR 拉镜像
kubectl create secret docker-registry sia-acr-cred \
  --namespace=sia \
  --docker-server=registry.cn-hangzhou.aliyuncs.com \
  --docker-username=<阿里云账号名> \
  --docker-password=<ACR 密码> \
  --docker-email=ops@example.com
```

---

## 8. 部署 SIA

### 8.1 准备 deployment.config.yaml

在 SIA 仓库根目录：

```bash
cp deploy/deployment.config.example.yaml deployment.config.yaml
```

打开 `deployment.config.yaml`，按下表填值（其余保持默认）：

| 字段 | 值（按你刚才记下的） |
|---|---|
| `cluster.context` | `<kubectl 当前 context 名>`（运行 `kubectl config current-context` 看） |
| `cluster.namespace` | `sia` |
| `image.registry` | `registry.cn-hangzhou.aliyuncs.com/sia` |
| `image.tag` | `v0.4.0` |
| `image.pullSecret` | `sia-acr-cred` |
| `host` | `sia.your-domain.com`（你的域名） |
| `mysql.host` | `rm-xxxxx.mysql.rds.aliyuncs.com` |
| `mysql.port` | `3306` |
| `mysql.user` | `sia` |
| `mysql.database` | `sia` |
| `mysql.password` | （RDS 高权限账号密码） |
| `redis.host` | `r-xxxxx.redis.rds.aliyuncs.com` |
| `redis.port` | `6379` |
| `redis.password` | （Redis 实例密码） |
| `minio.enabled` | `true` |
| `minio.host` | `oss-cn-hangzhou.aliyuncs.com` |
| `minio.port` | `443` |
| `minio.secure` | `true` |
| `minio.bucket` | `sia-reports-xxxxxx` |
| `minio.accessKey` | （RAM 子账号 AccessKey ID） |
| `minio.secretKey` | （RAM 子账号 AccessKey Secret） |
| `auth.adminPassword` | 强密码（首次登录用） |
| `llm.providers` | 至少配一个：Anthropic / OpenAI / 阿里云通义 / 本地 vLLM |

### 8.2 渲染 + 生成密钥

```bash
./scripts/deploy/configure.sh --generate-secrets
```

这条命令会：
- 读 `deployment.config.yaml`
- 生成 `deploy/helm/sia/values-prod.yaml`（已渲染的 Helm values）
- 生成 `deploy/rendered/sia-secrets.yaml`（K8s Secret manifest，含全部密钥）
- 自动生成 RS256 keypair 用于 JWT
- 自动校验弱密码、占位符

### 8.3 一键部署

```bash
./scripts/deploy/deploy-k8s.sh
```

它会按步骤：

1. 检查 `kubectl` / `helm` / `docker` 可用性
2. 解析 namespace 与 image registry
3. **跳过镜像构建**（你已经手工 push 到 ACR），如需重建加 `--skip-build`、`--skip-push`
4. 创建 namespace 并打 PSS=restricted 标签
5. **应用 Gatekeeper 约束**（如集群已装 Gatekeeper，否则自动跳过）
6. 应用 sia-secrets
7. `helm upgrade --install` 部署所有资源（API、consumer、web、ingress、PDB、HPA、CronJob、NetworkPolicy）
8. 等所有 Deployment 滚动完成
9. 跑 smoke test：`/health` 返 200 + 未鉴权 `/api/v1/intelligence` 返 401

预计 5-10 分钟完成。

### 8.4 验证 Pod

```bash
kubectl -n sia get pods
# 应看到（命名约定 helm release=sia）
# sia-api-xxxxxxxxx-xxxxx     1/1 Running
# sia-api-xxxxxxxxx-xxxxx     1/1 Running
# sia-consumer-xxxxxxxx-xxxxx 1/1 Running
# sia-web-xxxxxxxxx-xxxxx     1/1 Running

kubectl -n sia logs deploy/sia-api --tail=50
# 不应看到任何 Traceback；最后一行应是 Uvicorn 监听 0.0.0.0:8080
```

### 8.5 数据库迁移

如果 helm chart 没有自动跑 alembic（默认会通过 `migration-job.yaml` 跑一次），手动触发：

```bash
kubectl -n sia create job --from=cronjob/sia-migrate sia-migrate-once
# 或：
kubectl -n sia exec deploy/sia-api -- python scripts/ops/init_db.py
```

---

## 9. 公网访问：域名 + HTTPS

### 9.1 找到 Ingress 的公网 IP

```bash
kubectl -n kube-system get svc nginx-ingress-lb
# 或在 ACK 创建时勾了 ingress 时叫 nginx-ingress-controller
```

记下 `EXTERNAL-IP` 列（一串 IP，类似 `47.xxx.xxx.xxx`）。

### 9.2 域名解析

**控制台**：[云解析 DNS](https://dns.console.aliyun.com) → 选你的域名 → 解析设置：

| 记录类型 | 主机记录 | 解析值 |
|---|---|---|
| A | `sia` | `<上面的 EXTERNAL-IP>` |

如果你用其他 DNS 提供商，原理一样：A 记录指向 SLB IP。

中国大陆机房：A 记录绑定的子域名必须**已 ICP 备案**才能正常访问 80/443。

### 9.3 HTTPS 证书

#### 选项 A：阿里云免费 DV 证书（推荐试点）

**控制台**：[SSL 证书服务](https://yundunnext.console.aliyun.com/?p=cas) → 证书申请 → 免费 DV → 证书绑定域名 `sia.your-domain.com`

- 验证方式：DNS（最快）。
- 颁发后下载 **Nginx** 格式（含 `.pem` + `.key`）。
- 创建 K8s Secret：
  ```bash
  kubectl -n sia create secret tls sia-tls \
    --cert=fullchain.pem --key=private.key
  ```
- 修改 `deployment.config.yaml` 的 `tls.secretName: sia-tls`，重新 `./scripts/deploy/deploy-k8s.sh`。

#### 选项 B：cert-manager + Let's Encrypt（自动续期）

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@your-domain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF
```

然后在 ingress annotations 加 `cert-manager.io/cluster-issuer: letsencrypt-prod`。

### 9.4 第一次访问

打开浏览器：`https://sia.your-domain.com`

应看到 SIA 登录页。

默认账号：`admin` / 你在 `deployment.config.yaml` 设置的 `auth.adminPassword`。

**第一次登录后必做**：
1. 点右上角用户名 → 修改密码（启用强密码）。
2. 进入 **后台管理 → 用户管理**，创建分析师账号。
3. 进入 **后台管理 → API Key 管理**，为外部集成创建带最小 scope 的 key。

---

## 10. 验证与排错

### 10.1 健康检查

```bash
# 通过 SLB 公网访问
curl -k https://sia.your-domain.com/api/v1/health
# 应返回 {"status":"healthy","version":"...","database":"healthy","redis":"healthy"}

# 应返回 401（说明鉴权工作正常）
curl -k https://sia.your-domain.com/api/v1/intelligence
```

### 10.2 看 Pod 日志

```bash
# API 日志
kubectl -n sia logs -f deploy/sia-api

# Consumer 日志（处理流水线）
kubectl -n sia logs -f deploy/sia-consumer

# 看 ingress 日志
kubectl -n kube-system logs -f deploy/nginx-ingress-controller
```

### 10.3 常见问题

| 症状 | 原因 | 处理 |
|---|---|---|
| Pod 状态 `ImagePullBackOff` | ACR 拉取失败 | 检查 `sia-acr-cred` Secret + ACR 密码 |
| `CrashLoopBackOff` 启动报 MySQL 连接超时 | RDS 白名单 / 密码 / VPC 不对 | 检查 RDS 白名单含 `10.0.0.0/16`、VPC 是否同一个 |
| `/health` 返 503 `database=unhealthy` | 同上 | 同上 |
| Web 页面打开但 API 401 全部失败 | JWT secret 错配 | 重新跑 `./scripts/deploy/configure.sh --generate-secrets` |
| 域名打不开 | A 记录未生效 / 80/443 ICP 限制 | `nslookup sia.your-domain.com`、查备案状态 |
| 集群外 LLM 调用失败 | NetworkPolicy egress 默认 0.0.0.0/0，但 ACK Pod 出公网需 NAT 网关 | VPC 控制台 → 创建 **NAT 网关** + **EIP**，并把 vSwitch 加入 SNAT 入口 |

### 10.4 NAT 网关（让 Pod 出公网调 LLM API）

ACK 节点本身可能没有公网 IP。Pod 调 Anthropic / OpenAI / 通义需要 NAT。

**控制台**：[NAT 网关](https://vpcnext.console.aliyun.com) → 公网 NAT 网关 → 创建：

| 字段 | 值 |
|---|---|
| Region | 华东 1 |
| VPC | `sia-vpc` |
| 关联 vSwitch | 选三个之一 |
| EIP | 创建并绑定一个新 EIP |

创建后 → SNAT 入口 → 添加：源网段为整个 VPC（`10.0.0.0/16`），目的 EIP 即上面那个。

测试：
```bash
kubectl -n sia exec deploy/sia-api -- curl -sI https://api.anthropic.com/v1/messages
# 应返回 401（说明能出公网，只是缺 token；不是 connection timeout）
```

---

## 11. 后台管理界面快速上手

部署完成后，进入 `https://sia.your-domain.com`，左侧菜单：

| 菜单 | 角色可见 | 说明 |
|---|---|---|
| 仪表盘 | 全部 | KPI + 分类分布 + 优先级趋势图 |
| 情报中心 | 全部 | 列表 + 详情 + 重新分析 |
| 情报源管理 | analyst+ | 增删源、立即采集 |
| 报告管理 | 全部 | 日报 / 周报 / 应急简报 |
| **用户管理** | admin | 增改 / 停用 / 重置密码 |
| **API Key 管理** | admin | 创建（带 scope+role+TTL）、吊销 |
| **审计日志** | admin | 按 actor/event_type/时间 过滤 + 24h 统计 |
| **系统状态** | admin | Health / Circuit Breaker / Stream / DLQ / 调度任务 |

右上角：
- 🌐 **语言切换** 中文 / English
- 用户菜单 → 退出登录

---

## 12. 备份与日常运维

### 12.1 RDS 自动备份

[RDS 控制台](https://rdsnext.console.aliyun.com) → 选实例 → **备份恢复** → **修改备份策略**：

- 数据备份：每天，保留 7 天
- 日志备份：开启，保留 7 天

### 12.2 OSS 生命周期

OSS 控制台 → 选 Bucket → **基础设置** → 生命周期：

- 创建规则：≥ 30 天的 prefix `reports/` 转低频访问
- ≥ 365 天转归档

### 12.3 监控告警

ARMS Prometheus（ACK 创建时可一并装）+ Grafana：导入 `deploy/grafana/sia-overview.dashboard.json` 看 SLO 视图。

未装 ARMS：直接 `curl https://sia.your-domain.com/metrics` 也可，但需要外面接 Prometheus。

### 12.4 升级 SIA

```bash
git pull
TAG=v0.4.1
docker build -f deploy/docker/Dockerfile -t $REG/sia-backend:$TAG .
docker push $REG/sia-backend:$TAG
docker build -f deploy/docker/Dockerfile.web -t $REG/sia-web:$TAG .
docker push $REG/sia-web:$TAG

# 改 deployment.config.yaml 的 image.tag = v0.4.1
./scripts/deploy/deploy-k8s.sh --skip-build --skip-push
```

蓝绿 / 金丝雀升级：开启 `rollouts.enabled=true`（前置：集群装 Argo Rollouts 控制器）。

### 12.5 卸载 / 删除资源

**节省费用**：

```bash
# 卸载 SIA
helm -n sia uninstall sia
kubectl delete namespace sia
```

阿里云控制台释放：ACK 集群 → 释放（注意会删 SLB / NAT EIP，先解绑 EIP）；RDS / Redis / OSS Bucket 同理。

---

## 13. 安全加固清单（生产前必做）

| # | 项 | 验证 |
|---|---|---|
| 1 | RDS 启用 SSL 强制 | 控制台 → 数据安全性 → SSL 加密 → 开启；SIA 配置 `mysql.tlsMode: required` |
| 2 | Redis 启用 SSL | Redis 控制台 → SSL 加密 → 开启 |
| 3 | OSS 公网访问关闭 | Bucket → 权限管理 → 公共读写：私有 |
| 4 | RAM 子账号最小权限 | 自定义 policy 只允许指定 Bucket 读写 |
| 5 | ICP 备案完成 | 域名状态：已备案 |
| 6 | HTTPS + HSTS | 浏览器锁 + ingress 加 `nginx.ingress.kubernetes.io/configuration-snippet` |
| 7 | NetworkPolicy `egressAllowedCidrs` 收紧 | 改 `values-prod.yaml` 不再含 `0.0.0.0/0`，仅允许 LLM provider IP |
| 8 | 启用 Gatekeeper / Falco | ACK 应用市场可一键安装 |
| 9 | 镜像 Trivy 扫描 + Cosign 签名 | CI 已自带；ACR 企业版可再加准入校验 |
| 10 | 修改默认 admin 密码 | 首次登录后立即改 |
| 11 | API Key 全部带 TTL + scope | 进 API Key 管理排查 |

---

## 14. 参考链接

### 阿里云官方文档

- ACK 快速开始：<https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/getting-started/quick-start-for-first-time-users>
- ACK 创建托管集群：<https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/create-an-ack-managed-cluster-2/>
- ACK 网络规划：<https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/kubernetes-cluster-network-planning>
- RDS MySQL 创建实例：<https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/create-an-apsaradb-rds-for-mysql-instance-1>
- RDS MySQL 入门：<https://help.aliyun.com/zh/rds/apsaradb-rds-for-mysql/getting-started/>
- Tair / Redis 创建实例：<https://help.aliyun.com/zh/redis/getting-started/step-1-create-an-apsaradb-for-redis-instance>
- Redis 客户端连接：<https://help.aliyun.com/zh/redis/user-guide/use-a-client-to-connect-to-an-apsaradb-for-redis-instance>
- ACR 个人版创建：<https://help.aliyun.com/zh/acr/user-guide/create-a-container-registry-personal-edition-instance>
- ACR 推送镜像：<https://help.aliyun.com/zh/acr/user-guide/use-a-container-registry-personal-edition-instance-to-push-and-pull-images>
- OSS 创建 Bucket：<https://help.aliyun.com/zh/oss/user-guide/create-a-bucket-4>
- OSS 控制台快速入门：<https://help.aliyun.com/zh/oss/user-guide/console-quick-start>
- VPC 创建交换机：<https://help.aliyun.com/zh/vpc/user-guide/create-and-manage-vswitch>
- VPC 网络规划：<https://help.aliyun.com/zh/vpc/vpc-network-planning>

### SIA 项目内文档

- 部署：`docs/DEPLOYMENT_GUIDE.md`
- 配置参考：`docs/CONFIGURATION.md`
- 安全加固：`docs/SECURITY.md`（§11 检查项 + §12 漏洞披露）
- 运维 Runbook：`docs/OPERATIONS_GUIDE.md`
- API：`docs/API_REFERENCE.md`

---

*指南版本 2026-04-30 — 如对应 SIA 主版本变更，请同步刷新 §8 部分的 image tag 与 deployment.config.yaml 字段表。*
