# 运维运行手册

面向 SRE / DevOps 团队。覆盖发布、扩缩容、回滚、备份、故障排查、告警响应。

## 1. 环境变量约定

本文中：
- `$NS` = SIA 命名空间（默认 `sia`）
- `$RELEASE` = Helm release 名（默认 `sia`）

```bash
export NS=sia RELEASE=sia
```

## 2. 日常健康检查

### 2.1 一分钟概览
```bash
# Pod 状态
kubectl -n $NS get po -o wide

# 最近事件
kubectl -n $NS get events --sort-by=.lastTimestamp | tail -20

# Helm release
helm status $RELEASE -n $NS

# HPA
kubectl -n $NS get hpa

# Ingress 证书
kubectl -n $NS describe ingress sia-ingress | grep -A2 "TLS"
```

### 2.2 关键端点
```bash
kubectl -n $NS port-forward svc/sia-api 18080:8080 &
curl -s localhost:18080/api/v1/health | jq
curl -s localhost:18080/metrics | head
# 未鉴权的 resource 端点应返回 401
curl -i localhost:18080/api/v1/intelligence
```

## 3. 发布与升级

### 3.1 滚动升级到新版本
```bash
# 假设 CI 已构建并推送 v0.3.0 镜像
./scripts/deploy/deploy-k8s.sh -t v0.3.0 --skip-build --skip-push
```

`deploy-k8s.sh` 走 `helm upgrade --install --wait --timeout 5m`。滚动策略 `maxSurge: 1, maxUnavailable: 0`，零中断。

### 3.2 迁移 Job
post-install hook `sia-db-init-<rev>` 自动 `alembic upgrade head`。查看日志：
```bash
kubectl -n $NS logs job/sia-db-init-$(helm status $RELEASE -n $NS -o json | jq -r .version)
```

若迁移失败，Helm 会阻塞在该步。排查后手工：
```bash
kubectl -n $NS delete job -l app.kubernetes.io/component=migration
helm upgrade $RELEASE ...   # 重试
```

### 3.3 回滚
```bash
helm history  $RELEASE -n $NS
helm rollback $RELEASE <revision> -n $NS --wait
```

**注意**：向前迁移的 alembic 变更不会自动逆转。如果新版本引入了破坏性 schema 变更，回滚前需要先手工 `alembic downgrade <rev>`（在 Pod 内或临时 Pod 中执行）。

## 4. 扩缩容

### 4.1 API（已有 HPA）
HPA 按 CPU 70% 自动伸缩 2→8。手动临时拉高：
```bash
kubectl -n $NS patch hpa sia-api -p '{"spec":{"minReplicas":4}}'
```

### 4.2 Consumer（无 HPA）
Consumer 并行度 = replicas × consumer group 成员。**同一 consumer 组内 replicas 越多分片越细**：
```bash
kubectl -n $NS scale deploy/sia-consumer --replicas=3
```

注意：每个 pod 自己的 `consumer_name` 在代码里硬编码为 `analyzer-1`。**如需多实例消费**，需修改 `sia/analyzer/pipeline.py` 里的 `consumer_name` 读取 `HOSTNAME` 或 pod 序号。

### 4.3 Web
```bash
kubectl -n $NS scale deploy/sia-web --replicas=3
```

## 5. 排障 Runbook

### 5.1 Pod CrashLoopBackOff

```bash
POD=$(kubectl -n $NS get po -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}')
kubectl -n $NS logs $POD --previous          # 崩溃前日志
kubectl -n $NS describe po $POD | grep -A10 "Last State"
```

常见原因：

| 日志关键字 | 原因 | 处理 |
|---|---|---|
| `SIA_AUTH_JWT_SECRET is required` | Secret 未挂载 / 未 apply | `kubectl -n $NS get secret sia-secrets`；重 apply；`rollout restart` |
| `SIA_AUTH_JWT_SECRET uses a placeholder value` | 生产还在 `change-me-in-production` 等默认值 | 正确生成 Secret |
| `RS256 selected but SIA_AUTH_JWT_PRIVATE_KEY is empty` | 切换 RS256 后未提供密钥对 | `configure.sh --generate-secrets` |
| `SIA_MYSQL_PASSWORD is required in production` | Secret 缺字段 | 检查 `sia-secrets` keys |
| `Default 'minioadmin' credentials are not allowed in production` | 未覆盖 MinIO 默认值 | 填 `secrets.minioAccessKey/SecretKey` |
| `Permission denied: /tmp/...` | emptyDir 没挂对 | `kubectl -n $NS get po $POD -o yaml \| grep -A2 volumeMounts` |
| `MySQL ... 1045 Access denied` | DB 密码错 / 用户不存在 / TLS 问题 | 从 Pod 内 `mysql -h $SIA_MYSQL_HOST -u$SIA_MYSQL_USER -p` 手工验证 |
| `redis.exceptions.AuthenticationError` | Redis 密码错 | 从 Pod 内 `redis-cli -h ... -a ...` 验证 |

### 5.2 pod Ready 但 502 Bad Gateway
- Ingress → Service 关联 label 不匹配：`kubectl -n $NS describe svc sia-api`
- Pod port != Service targetPort：`kubectl -n $NS get svc sia-api -o yaml | grep -i port`
- nginx 前端返回 502：`kubectl -n $NS logs deploy/sia-web`

### 5.3 Consumer 不消费
```bash
# Stream 是否有积压
kubectl -n $NS exec -it $(kubectl -n $NS get po -l app.kubernetes.io/component=consumer -o jsonpath='{.items[0].metadata.name}') -- \
  sh -c 'redis-cli -h $SIA_REDIS_HOST ${SIA_REDIS_PASSWORD:+-a $SIA_REDIS_PASSWORD} XLEN raw_intel_stream'

# 消费者组状态
  redis-cli ... XINFO GROUPS raw_intel_stream

# DLQ 积压
  redis-cli ... XLEN dead_letter_stream
```

如果 `pending` 数持续上涨：
- 查看 consumer 日志 grep "Analysis consumer error"
- 检查 LLM 提供商可达性：进入 Pod `curl -m 10 https://generativelanguage.googleapis.com`
- 检查 DB 写入延迟：`SHOW PROCESSLIST`

### 5.4 LLM 调用失败激增
1. `llm_call_log` 表统计：
   ```sql
   SELECT provider, model, COUNT(*) fail
   FROM llm_call_log
   WHERE success=0 AND created_at > NOW() - INTERVAL 10 MINUTE
   GROUP BY provider, model;
   ```
2. 熔断触发：consumer 日志 grep `circuit breaker OPEN`
3. 应急切换默认模型：修改 `config/llm_gateway.yaml` `default_model`，`rollout restart`

### 5.5 磁盘 / 内存飙升
- 后端 / 消费者内存通常稳定在 400-800 MiB；超过 1.5 GiB 检查 huggingface 缓存是否爆（`/home/sia/.cache/huggingface`，emptyDir sizeLimit 2 GiB）
- MySQL 存储：`SELECT table_schema, SUM(data_length+index_length)/1024/1024 MB FROM information_schema.tables GROUP BY 1`
- Redis：`INFO memory`；维护 `MAXMEMORY-POLICY allkeys-lru`

## 6. 备份与恢复

SIA 不存自备份层；依赖平台：

| 数据 | 备份方案 |
|---|---|
| MySQL | 平台托管 RDS 自动快照（建议 PITR 7d） |
| Redis | AOF 持久化 + 定时 RDB；若 Redis 主要作为队列/缓存，丢失可接受 |
| MinIO | 开启版本控制 + 跨桶复制（对 `sia-reports` 桶） |
| Milvus | 使用 Milvus Backup 工具；向量可由 MySQL 情报重建 |
| K8s 配置 | `helm get values $RELEASE -n $NS` 归档；Secret 来源（Vault / External Secrets）自备份 |

灾难恢复顺序：MySQL → Redis → Milvus → MinIO → SIA（helm install）。

## 7. Secret 轮换

### 7.1 定期轮换 JWT（推荐 90 天）
```bash
# 生成新 JWT 密钥
$EDITOR deployment.config.yaml            # 把 secrets.jwtSecret 置空
./scripts/deploy/configure.sh --generate-secrets
kubectl apply -f deploy/rendered/sia-secrets.yaml
kubectl rollout restart deploy -n $NS
# 旧 access token 会在过期时（默认 30 min）自然失效；refresh token 7 天
```

**RS256 场景**：可以滚动更新 —— 保留旧 public key 识别旧 token，新 private key 签新 token。当前 chart 尚未实现多 key 并存，如需零中断轮换建议过渡到 KMS 方案。

### 7.2 数据库密码
1. 先在 DB 创建新用户或新密码
2. 更新 `deployment.config.yaml` → `configure.sh`
3. apply + rollout restart
4. 确认 API 恢复健康后废弃旧密码

## 8. 审计日志分析

结构化 JSON，`logger=sia.audit`。每个事件字段：`ts, event, actor_id, actor_name, target, target_id, result, ip, method, path, ua`。

常用查询（Loki / Splunk）：

```
# 今日失败登录 top 10 来源
{app="sia"} | json | logger="sia.audit" | event="user.login" | result="failure" | stats count by ip | sort count desc | limit 10

# 管理员操作审计
{app="sia"} | json | logger="sia.audit" | target="admin" | line_format "{{.ts}} {{.actor_name}} {{.event}} -> {{.result}}"

# 异常的 report 导出
{app="sia"} | json | logger="sia.audit" | event="report.export" | actor_name!~"(admin|sia-service)"
```

## 9. 监控告警建议

| 指标 | 阈值 | 含义 |
|---|---|---|
| `sia_api_request_errors_total{code=~"5.."}` / 5m | > 1% | API 5xx 率偏高 |
| `container_cpu_usage_seconds_total{pod=~"sia-.*"}` | > 80% sustained 10m | HPA 打满或单 pod 过载 |
| `redis_streams_length{stream="raw_intel_stream"}` | > 1000 | 消费者跟不上 |
| `redis_streams_length{stream="dead_letter_stream"}` | > 0 持续 | 有毒消息 |
| MySQL slow_query count | > 10 / 5m | 索引退化或查询变动 |
| `kube_deployment_status_replicas_unavailable{deployment=~"sia-.*"}` | > 0 | 实例 Ready 不足 |
| `sia_audit{event="user.login",result="failure"}` count | > 20 / 5m from same IP | 暴破 |

## 10. 灾变演练

每季度建议：

1. **Pod kill**：`kubectl delete po sia-api-xxx`，观察 Ready + 请求是否有失败
2. **节点漏失**：`kubectl cordon` + `drain` 一台节点，观察 topologySpread 是否重新铺开
3. **DB 临时不可达**：网络策略临时阻塞 MySQL Service，观察 liveness/readiness 表现
4. **回滚演练**：`helm rollback` 到上一版本，再前滚

## 11. 日常维护命令速查

```bash
# 查看当前 release 配置
helm get values $RELEASE -n $NS

# 查看即将 apply 的 manifest
helm template $RELEASE ./deploy/helm/sia -f deploy/helm/sia/values-prod.yaml

# 强制重启所有 workload（读取最新 Secret/ConfigMap）
kubectl -n $NS rollout restart deployment

# 临时注入 shell 调试（注意：container readOnlyRootFS，kubectl debug 会启新容器）
kubectl -n $NS debug $(kubectl -n $NS get po -l app.kubernetes.io/component=api -o name | head -1) \
  --image=busybox:1.36 --target=sia-api

# 进入 DB
kubectl -n $NS run mysql-client --rm -it --restart=Never --image=mysql:8.0 -- \
  mysql -h $MYSQL_HOST -u$MYSQL_USER -p$MYSQL_PASS sia

# 查询最近 LLM 账单
kubectl -n $NS run mysql-client ... -- \
  mysql ... -e "SELECT provider, model, SUM(input_tokens+output_tokens) FROM llm_call_log WHERE created_at > NOW() - INTERVAL 1 DAY GROUP BY 1,2"
```

## 12. 退役（下线）

```bash
# 全量删除，保留数据
helm uninstall $RELEASE -n $NS
# Secret、ConfigMap、PVC 由 kubectl 单独清理（若使用）
kubectl -n $NS delete secret sia-secrets
kubectl delete ns $NS    # 彻底下线
```

**不可逆**：务必在执行前确认 MySQL/Milvus/MinIO 等外部存储的归档与合规要求。

---

*SIA v0.2.0 | Operations Guide*
