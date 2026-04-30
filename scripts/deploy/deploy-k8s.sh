#!/bin/bash
set -euo pipefail

# =============================================================================
# SIA — One-Click Kubernetes Deployment
#
# Typical flow:
#   cp deploy/deployment.config.example.yaml deployment.config.yaml
#   vim deployment.config.yaml                          # fill placeholders
#   ./scripts/deploy/configure.sh --generate-secrets    # generates values-prod.yaml + sia-secrets.yaml
#   ./scripts/deploy/deploy-k8s.sh                      # builds + pushes + helm upgrade + smoke test
#
# Alt (CI path, already-built images):
#   ./scripts/deploy/deploy-k8s.sh --skip-build --skip-push -t v0.2.0
#
# Prerequisites:
#   - kubectl configured with target cluster context
#   - helm v3.12+
#   - docker (for building images; not needed if --skip-build)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHART_DIR="$PROJECT_ROOT/deploy/helm/sia"
CONFIG_FILE="$PROJECT_ROOT/deployment.config.yaml"
VALUES_PROD="$CHART_DIR/values-prod.yaml"
SECRETS_YAML="$PROJECT_ROOT/deploy/rendered/sia-secrets.yaml"

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Defaults ─────────────────────────────────────────────────────────────────
RELEASE_NAME="sia"
NAMESPACE=""
VALUES_FILE=""
SKIP_BUILD=false
SKIP_PUSH=false
SKIP_SMOKE=false
DRY_RUN=false
DIFF_ONLY=false
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo '0.2.0')}"

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    -c|--config)       CONFIG_FILE="$2"; shift 2 ;;
    -f|--values)       VALUES_FILE="$2"; shift 2 ;;
    -n|--namespace)    NAMESPACE="$2"; shift 2 ;;
    -t|--tag)          IMAGE_TAG="$2"; shift 2 ;;
    --skip-build)      SKIP_BUILD=true; shift ;;
    --skip-push)       SKIP_PUSH=true; shift ;;
    --skip-smoke)      SKIP_SMOKE=true; shift ;;
    --dry-run)         DRY_RUN=true; shift ;;
    --diff)            DIFF_ONLY=true; shift ;;
    -h|--help)
      cat <<EOF
Usage: $0 [options]

Options:
  -c, --config FILE     Centralized config (default: ./deployment.config.yaml)
  -f, --values FILE     Extra Helm values file (merged after values-prod.yaml)
  -n, --namespace NS    Override namespace (default: read from config)
  -t, --tag TAG         Docker image tag (default: git short SHA)
  --skip-build          Skip Docker image build
  --skip-push           Skip pushing images to registry
  --skip-smoke          Skip post-deploy smoke test
  --dry-run             Helm dry-run only (no actual deploy)
  --diff                Only show helm template diff vs current release, no deploy
  -h, --help            Show this help

Typical first run:
  ./scripts/deploy/configure.sh --generate-secrets
  $0
EOF
      exit 0 ;;
    *) err "Unknown option: $1" ;;
  esac
done

# =============================================================================
# Step 0 — Prerequisites
# =============================================================================
info "Step 0/8 — Checking prerequisites..."

for cmd in kubectl helm; do
  command -v "$cmd" &>/dev/null || err "$cmd is required but not found"
done
if [[ "$SKIP_BUILD" == false ]]; then
  command -v docker &>/dev/null || err "docker is required (or use --skip-build)"
fi
kubectl cluster-info &>/dev/null || err "kubectl cannot reach the cluster. Check your kubeconfig."

KUBE_CONTEXT=$(kubectl config current-context)
info "Cluster context: $KUBE_CONTEXT"

# =============================================================================
# Step 1 — Resolve centralized config
# =============================================================================
info "Step 1/8 — Resolving configuration..."

if [[ -f "$CONFIG_FILE" ]]; then
  info "Found $CONFIG_FILE — config-driven mode"
  if [[ ! -f "$VALUES_PROD" || ! -f "$SECRETS_YAML" ]]; then
    warn "values-prod.yaml or sia-secrets.yaml missing — running configure.sh..."
    "$SCRIPT_DIR/configure.sh" -c "$CONFIG_FILE" || err "configure.sh failed"
  fi
  [[ -z "$NAMESPACE" ]] && NAMESPACE="$(grep -E '^\s*namespace:' "$VALUES_PROD" | head -1 | awk '{print $2}' | tr -d '"')"
  REGISTRY=$(grep -E '^\s*imageRegistry:' "$VALUES_PROD" | head -1 | awk '{print $2}' | tr -d '"')
elif [[ -n "$VALUES_FILE" ]]; then
  info "No central config, using --values file: $VALUES_FILE"
  [[ -f "$VALUES_FILE" ]] || err "Values file not found: $VALUES_FILE"
  [[ -z "$NAMESPACE" ]] && NAMESPACE="sia"
  REGISTRY="${SIA_IMAGE_REGISTRY:-}"
else
  err "No deployment.config.yaml found, and no -f VALUES_FILE given.
Run: cp deploy/deployment.config.example.yaml deployment.config.yaml"
fi

: "${NAMESPACE:=sia}"
BACKEND_IMAGE="${REGISTRY:+$REGISTRY/}sia-backend:${IMAGE_TAG}"
WEB_IMAGE="${REGISTRY:+$REGISTRY/}sia-web:${IMAGE_TAG}"

info "Target namespace: $NAMESPACE"
info "Image tag:        $IMAGE_TAG"
info "Backend image:    $BACKEND_IMAGE"
info "Web image:        $WEB_IMAGE"
ok "Configuration resolved"

# =============================================================================
# Step 2 — Build images
# =============================================================================
if [[ "$SKIP_BUILD" == true ]]; then
  warn "Step 2/8 — Skipping image build (--skip-build)"
else
  info "Step 2/8 — Building Docker images..."
  cd "$PROJECT_ROOT"
  docker build -f deploy/docker/Dockerfile     -t "$BACKEND_IMAGE" --build-arg BUILDKIT_INLINE_CACHE=1 .
  docker build -f deploy/docker/Dockerfile.web -t "$WEB_IMAGE"     .
  ok "Images built"
fi

# =============================================================================
# Step 3 — Push images
# =============================================================================
if [[ "$SKIP_PUSH" == true ]]; then
  warn "Step 3/8 — Skipping image push (--skip-push)"
elif [[ -z "$REGISTRY" ]]; then
  warn "Step 3/8 — No registry configured, using local images"
else
  info "Step 3/8 — Pushing images..."
  docker push "$BACKEND_IMAGE"
  docker push "$WEB_IMAGE"
  ok "Images pushed"
fi

# =============================================================================
# Step 4 — Create namespace + Pod Security Standards labels (DEP-3)
# =============================================================================
info "Step 4/8 — Ensuring namespace $NAMESPACE exists..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
# Enforce the restricted PSS profile so any future drift (someone landing
# a privileged pod) is rejected at admission time, not in code review.
kubectl label namespace "$NAMESPACE" \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/enforce-version=latest \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted \
  --overwrite >/dev/null
ok "Namespace ready (PSS=restricted)"

# =============================================================================
# Step 5 — Apply secrets manifest (if present)
# =============================================================================
info "Step 5/8 — Applying secrets..."
if [[ -f "$SECRETS_YAML" ]]; then
  kubectl apply -f "$SECRETS_YAML"
  ok "Secrets applied from $SECRETS_YAML"
else
  warn "No rendered secrets file. Ensure sia-secrets already exists in namespace $NAMESPACE."
  kubectl -n "$NAMESPACE" get secret sia-secrets >/dev/null 2>&1 \
    || err "sia-secrets not found in namespace. Run: ./scripts/deploy/configure.sh --generate-secrets"
fi

# =============================================================================
# Step 5b — Apply Gatekeeper constraints (DEP-2)
# =============================================================================
# When the cluster has Gatekeeper installed, automatically enforce the
# constraint templates / constraints checked into deploy/k8s/. We detect
# Gatekeeper by the presence of its CRDs; absence is not a failure.
GATEKEEPER_DIR="$PROJECT_ROOT/deploy/k8s/gatekeeper-constraints"
if [[ -d "$GATEKEEPER_DIR" ]]; then
  info "Step 5b/8 — Applying Gatekeeper constraints (if available)..."
  if kubectl api-resources --api-group=templates.gatekeeper.sh 2>/dev/null | grep -q "constrainttemplates"; then
    if kubectl apply -f "$GATEKEEPER_DIR/" 2>&1 | tee /tmp/sia-gk-apply.log; then
      ok "Gatekeeper constraints applied"
    else
      warn "Gatekeeper apply hit errors — see /tmp/sia-gk-apply.log"
    fi
  else
    warn "Gatekeeper CRDs not detected; skipping constraint apply"
    warn "  (install gatekeeper operator first to enforce SIA's policies)"
  fi
fi

# =============================================================================
# Step 6 — Helm upgrade / install
# =============================================================================
info "Step 6/8 — Deploying via Helm..."

HELM_ARGS=(
  upgrade --install "$RELEASE_NAME" "$CHART_DIR"
  --namespace "$NAMESPACE"
  --set "api.image.tag=$IMAGE_TAG"
  --set "consumer.image.tag=$IMAGE_TAG"
  --set "web.image.tag=$IMAGE_TAG"
  --set "namespace=$NAMESPACE"
)

[[ -f "$VALUES_PROD" ]] && HELM_ARGS+=(-f "$VALUES_PROD")
[[ -n "$VALUES_FILE" && -f "$VALUES_FILE" ]] && HELM_ARGS+=(-f "$VALUES_FILE")

if [[ "$DIFF_ONLY" == true ]]; then
  info "Showing helm template diff only (no apply)..."
  helm template "${HELM_ARGS[@]:1}" > /tmp/sia-next.yaml
  kubectl -n "$NAMESPACE" get all -o yaml > /tmp/sia-current.yaml 2>/dev/null || true
  diff -u /tmp/sia-current.yaml /tmp/sia-next.yaml | head -200 || true
  exit 0
fi

if [[ "$DRY_RUN" == true ]]; then
  HELM_ARGS+=(--dry-run --debug)
  info "Dry-run mode — no changes will be made"
fi

HELM_ARGS+=(--wait --timeout 5m)

helm "${HELM_ARGS[@]}"
ok "Helm deployment complete"

# =============================================================================
# Step 7 — Rollout status
# =============================================================================
if [[ "$DRY_RUN" == true ]]; then
  info "Dry-run complete"
  exit 0
fi

info "Step 7/8 — Waiting for rollout..."
kubectl rollout status deployment/sia-api      -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/sia-consumer -n "$NAMESPACE" --timeout=180s || warn "consumer not ready in time"
kubectl rollout status deployment/sia-web      -n "$NAMESPACE" --timeout=120s || warn "web not ready in time"
ok "Rollout complete"

# =============================================================================
# Step 8 — Smoke test
# =============================================================================
if [[ "$SKIP_SMOKE" == true ]]; then
  warn "Step 8/8 — Skipping smoke test (--skip-smoke)"
else
  info "Step 8/8 — Running smoke tests..."
  kubectl port-forward svc/sia-api 18080:8080 -n "$NAMESPACE" &>/dev/null &
  PF_PID=$!
  trap "kill $PF_PID 2>/dev/null || true" EXIT
  sleep 3

  SMOKE_FAIL=0
  for i in 1 2 3; do
    code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:18080/api/v1/health || echo "000")
    if [[ "$code" == "200" ]]; then
      ok "  health check $i/3: HTTP 200"
    else
      warn "  health check $i/3: HTTP $code"
      SMOKE_FAIL=$((SMOKE_FAIL+1))
    fi
  done

  code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:18080/api/v1/intelligence || echo "000")
  if [[ "$code" == "401" || "$code" == "403" ]]; then
    ok "  authz check: HTTP $code (expected 401/403 without credentials)"
  else
    warn "  authz check: HTTP $code (expected 401/403)"
    SMOKE_FAIL=$((SMOKE_FAIL+1))
  fi

  kill $PF_PID 2>/dev/null || true
  trap - EXIT

  [[ $SMOKE_FAIL -eq 0 ]] && ok "Smoke tests passed" || warn "Smoke tests had $SMOKE_FAIL failure(s)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  SIA Deployment Complete${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  Namespace  : ${CYAN}$NAMESPACE${NC}"
echo -e "  Release    : ${CYAN}$RELEASE_NAME${NC}"
echo -e "  Image Tag  : ${CYAN}$IMAGE_TAG${NC}"
echo -e "  Cluster    : ${CYAN}$KUBE_CONTEXT${NC}"
echo ""
echo -e "  ${YELLOW}Quick access:${NC}"
echo -e "    kubectl port-forward svc/sia-api 8080:8080 -n $NAMESPACE"
echo ""
echo -e "  ${YELLOW}Helm management:${NC}"
echo -e "    helm status $RELEASE_NAME -n $NAMESPACE"
echo -e "    helm history $RELEASE_NAME -n $NAMESPACE"
echo -e "    helm rollback $RELEASE_NAME <revision> -n $NAMESPACE"
echo ""
