#!/bin/bash
# ================================================================
# 安全情报分析智能体 — 一键部署脚本
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================
# 使用说明：
#   1. 确保已安装 kubectl、helm、docker，且 kubectl 已配置正确的 K8s 上下文
#   2. 修改 helm/values-prod.yaml 中的配置
#   3. 预先在 K8s 中创建 Secrets（或使用本脚本的交互模式）
#   4. 执行：bash scripts/setup.sh [--dry-run] [--skip-images]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="intel-system"
HELM_RELEASE="intel-agent"
VALUES_FILE="${ROOT_DIR}/helm/values.yaml"
PROD_VALUES="${ROOT_DIR}/helm/values-prod.yaml"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

DRY_RUN=false
SKIP_IMAGES=false
for arg in "$@"; do
    case "$arg" in
        --dry-run)     DRY_RUN=true ;;
        --skip-images) SKIP_IMAGES=true ;;
    esac
done

echo ""
echo "================================================================"
echo "  安全情报分析智能体 v1.0 — 一键部署脚本"
echo "  作者：alex (unix_sec@163.com)"
echo "================================================================"
echo ""

# ---- 前置检查 ----
log_info "检查前置依赖..."

for cmd in kubectl helm docker; do
    if ! command -v "$cmd" &>/dev/null; then
        log_error "未找到命令：$cmd，请先安装。"
        exit 1
    fi
    log_ok "$cmd 已就绪"
done

# 检查 K8s 连通性
if ! kubectl cluster-info &>/dev/null; then
    log_error "无法连接 K8s 集群，请检查 kubeconfig。"
    exit 1
fi
log_ok "K8s 集群连通正常：$(kubectl config current-context)"

# ---- 选择 values 文件 ----
if [ -f "$PROD_VALUES" ]; then
    log_info "使用生产配置：${PROD_VALUES}"
    VALUES_ARGS="-f ${VALUES_FILE} -f ${PROD_VALUES}"
else
    log_warn "未找到 values-prod.yaml，使用默认 values.yaml（仅用于测试）"
    VALUES_ARGS="-f ${VALUES_FILE}"
fi

# ---- 构建 Docker 镜像（可跳过） ----
if [ "$SKIP_IMAGES" = "false" ]; then
    log_info "构建 Docker 镜像..."
    REGISTRY=$(grep "imageRegistry" "${VALUES_FILE}" | awk '{print $2}')

    for component in admin-api rss-collector web-collector search-collector; do
        case "$component" in
            admin-api)       dir="${ROOT_DIR}/admin-api" ;;
            rss-collector)   dir="${ROOT_DIR}/collectors" ;;
            web-collector)   dir="${ROOT_DIR}/collectors" ;;
            search-collector)dir="${ROOT_DIR}/collectors" ;;
        esac

        IMAGE="${REGISTRY}/intel/${component}:1.0"
        log_info "构建 ${IMAGE}..."
        if [ "$DRY_RUN" = "false" ]; then
            docker build -t "$IMAGE" -f "${dir}/${component//-/_}/Dockerfile" "${dir}" || \
            docker build -t "$IMAGE" "${dir}"
            docker push "$IMAGE"
        else
            log_info "[DRY-RUN] 跳过构建 ${IMAGE}"
        fi
    done

    # 前端
    FRONTEND_IMAGE="${REGISTRY}/intel/admin-web:1.0"
    log_info "构建 ${FRONTEND_IMAGE}..."
    if [ "$DRY_RUN" = "false" ]; then
        docker build -t "$FRONTEND_IMAGE" "${ROOT_DIR}/admin-web"
        docker push "$FRONTEND_IMAGE"
    fi
fi

# ---- 创建 Namespace ----
log_info "创建 Namespace: ${NAMESPACE}..."
if [ "$DRY_RUN" = "false" ]; then
    kubectl apply -f "${ROOT_DIR}/helm/templates/namespace.yaml"
else
    log_info "[DRY-RUN] 跳过 Namespace 创建"
fi

# ---- 提示手动创建 Secrets ----
echo ""
log_warn "================================================================"
log_warn "  重要：请确保以下 K8s Secrets 已创建（包含真实凭证）："
log_warn "  - mysql-credentials"
log_warn "  - llm-credentials"
log_warn "  - search-api-credentials"
log_warn "  - wecom-bot-credentials"
log_warn "  - smtp-credentials"
log_warn "  - sms-gw-credentials"
log_warn "  - dify-api-credentials"
log_warn ""
log_warn "  参考：helm/templates/secrets.yaml（替换占位符后 kubectl apply）"
log_warn "================================================================"
echo ""

read -p "Secrets 是否已创建完毕？[y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    log_error "请先创建 Secrets 后再继续。"
    exit 1
fi

# ---- Helm 部署 ----
log_info "执行 Helm 部署..."
HELM_CMD="helm upgrade --install ${HELM_RELEASE} ${ROOT_DIR}/helm \
    --namespace ${NAMESPACE} \
    --create-namespace \
    ${VALUES_ARGS} \
    --wait --timeout 5m"

if [ "$DRY_RUN" = "true" ]; then
    log_info "[DRY-RUN] 执行：${HELM_CMD} --dry-run"
    eval "${HELM_CMD} --dry-run"
else
    eval "${HELM_CMD}"
fi

# ---- 初始化数据库 ----
if [ "$DRY_RUN" = "false" ]; then
    log_info "等待 MySQL 就绪..."
    kubectl wait --for=condition=Ready pod -l app=mysql-primary \
        -n ${NAMESPACE} --timeout=120s

    log_info "初始化数据库 schema..."
    MYSQL_POD=$(kubectl get pods -n ${NAMESPACE} -l app=mysql-primary -o jsonpath='{.items[0].metadata.name}')
    kubectl exec -n ${NAMESPACE} "${MYSQL_POD}" -- \
        mysql -u root -p"$(kubectl get secret mysql-credentials -n ${NAMESPACE} -o jsonpath='{.data.password}' | base64 -d)" \
        < "${ROOT_DIR}/database/ddl.sql"

    log_info "初始化种子数据..."
    kubectl exec -n ${NAMESPACE} "${MYSQL_POD}" -- \
        mysql -u root -p"$(kubectl get secret mysql-credentials -n ${NAMESPACE} -o jsonpath='{.data.password}' | base64 -d)" \
        < "${ROOT_DIR}/database/seed.sql"
fi

# ---- 验证部署 ----
log_info "验证部署状态..."
if [ "$DRY_RUN" = "false" ]; then
    kubectl get pods -n ${NAMESPACE}
    kubectl get services -n ${NAMESPACE}
    kubectl get ingress -n ${NAMESPACE} 2>/dev/null || true
fi

echo ""
log_ok "================================================================"
log_ok "  部署完成！"
log_ok "  管理控制台：http://intel-admin.internal.company.com"
log_ok "  API 文档：  http://intel-api.internal.company.com/docs"
log_ok "  Grafana：   http://grafana.internal.company.com"
log_ok "================================================================"
log_ok "  下一步：运行 python scripts/test-llm.py 验证 LLM 连通性"
echo ""
