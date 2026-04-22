#!/bin/bash
set -euo pipefail

# =============================================================================
# SIA — One-Click Configuration Renderer
#
# Reads a centralized deployment.config.yaml and produces:
#   1. deploy/helm/sia/values-prod.yaml       (non-secret Helm values)
#   2. deploy/rendered/sia-secrets.yaml       (K8s Secret manifest, chmod 600)
#   3. deploy/rendered/sia-tls-ca-*.yaml      (TLS CA Secret stubs, if referenced)
#
# Usage:
#   ./scripts/deploy/configure.sh                           # use ./deployment.config.yaml
#   ./scripts/deploy/configure.sh -c path/to/config.yaml
#   ./scripts/deploy/configure.sh --generate-secrets        # auto-fill empty/<...> secrets
#   ./scripts/deploy/configure.sh --check-only              # validate placeholders, no render
#
# The script never talks to the cluster. Follow up with deploy-k8s.sh.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CONFIG_FILE="$PROJECT_ROOT/deployment.config.yaml"
GENERATE_SECRETS=false
CHECK_ONLY=false

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case $1 in
    -c|--config)         CONFIG_FILE="$2"; shift 2 ;;
    --generate-secrets)  GENERATE_SECRETS=true; shift ;;
    --check-only)        CHECK_ONLY=true; shift ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) err "Unknown option: $1" ;;
  esac
done

# -----------------------------------------------------------------------------
# Prerequisites
# -----------------------------------------------------------------------------
command -v yq       >/dev/null || err "yq (https://github.com/mikefarah/yq) is required"
command -v openssl  >/dev/null || err "openssl is required"

YQ_VERSION=$(yq --version 2>&1 | head -1)
case "$YQ_VERSION" in
  *"mikefarah"*|*"version v4"*|*"version 4"*) : ;;
  *) err "yq must be mikefarah/yq v4.x, found: $YQ_VERSION" ;;
esac

[[ -f "$CONFIG_FILE" ]] || err "Config file not found: $CONFIG_FILE
Run: cp deploy/deployment.config.example.yaml deployment.config.yaml"

info "Reading config: $CONFIG_FILE"

# -----------------------------------------------------------------------------
# Step 1: Placeholder validation
# -----------------------------------------------------------------------------
info "Validating placeholders..."

# Fields that MUST be replaced (non-secret, no auto-generate).
REQUIRED_FIELDS=(
  ".cluster.context"
  ".cluster.namespace"
  ".registry.url"
  ".ingress.host"
  ".mysql.host"
  ".redis.host"
  ".milvus.host"
)

MISSING=()
for f in "${REQUIRED_FIELDS[@]}"; do
  v=$(yq -r "$f // \"\"" "$CONFIG_FILE")
  if [[ -z "$v" || "$v" =~ ^\<.*\>$ ]]; then
    MISSING+=("$f  (current: \"$v\")")
  fi
done

# MinIO host only required when enabled
MINIO_ENABLED=$(yq -r ".minio.enabled // false" "$CONFIG_FILE")
if [[ "$MINIO_ENABLED" == "true" ]]; then
  v=$(yq -r ".minio.host // \"\"" "$CONFIG_FILE")
  [[ -z "$v" || "$v" =~ ^\<.*\>$ ]] && MISSING+=(".minio.host  (current: \"$v\")")
fi

# TLS secretName OR clusterIssuer is required when tls.enabled
TLS_ENABLED=$(yq -r ".ingress.tls.enabled // false" "$CONFIG_FILE")
if [[ "$TLS_ENABLED" == "true" ]]; then
  SN=$(yq -r ".ingress.tls.secretName // \"\"" "$CONFIG_FILE")
  CI=$(yq -r ".ingress.tls.clusterIssuer // \"\"" "$CONFIG_FILE")
  if [[ ( -z "$SN" || "$SN" =~ ^\<.*\>$ ) && ( -z "$CI" || "$CI" =~ ^\<.*\>$ ) ]]; then
    MISSING+=(".ingress.tls.secretName OR .ingress.tls.clusterIssuer (one must be set)")
  fi
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
  err "The following required fields still contain placeholders:
$(printf '  - %s\n' "${MISSING[@]}")
Edit $CONFIG_FILE and rerun."
fi

ok "All required placeholders are filled"

# -----------------------------------------------------------------------------
# Step 2: Secret validation / auto-generation
# -----------------------------------------------------------------------------
info "Processing secrets..."

# Map: key -> generator command (empty string means no auto-gen, must be user-provided)
declare -A SECRET_GEN=(
  [".secrets.jwtSecret"]="openssl rand -hex 32"
  [".secrets.apiKey"]="openssl rand -hex 32"
  [".secrets.adminPassword"]="openssl rand -base64 24 | tr -d '=+/' | cut -c1-20"
  [".secrets.mysqlPassword"]=""          # user must provide (must match external DB)
  [".secrets.redisPassword"]=""          # same
  [".secrets.minioAccessKey"]="openssl rand -hex 16"
  [".secrets.minioSecretKey"]="openssl rand -base64 32 | tr -d '=+/' | cut -c1-40"
)

# Algorithm-gated requirement
JWT_ALG=$(yq -r ".secrets.jwtAlgorithm // \"HS256\"" "$CONFIG_FILE")
info "JWT algorithm: $JWT_ALG"

EMPTY_SECRETS=()
TMP_CONFIG="$(mktemp)"
cp "$CONFIG_FILE" "$TMP_CONFIG"

is_placeholder() {
  local v="$1"
  [[ -z "$v" || "$v" =~ ^\<.*\>$ ]]
}

for key in "${!SECRET_GEN[@]}"; do
  current=$(yq -r "$key // \"\"" "$TMP_CONFIG")
  if is_placeholder "$current"; then
    gen="${SECRET_GEN[$key]}"
    if [[ "$GENERATE_SECRETS" == true && -n "$gen" ]]; then
      new_val=$(bash -c "$gen")
      yq -i "$key = \"$new_val\"" "$TMP_CONFIG"
      info "  auto-generated $key"
    else
      EMPTY_SECRETS+=("$key")
    fi
  fi
done

# MinIO host + credentials only required when minio.enabled
if [[ "$MINIO_ENABLED" != "true" ]]; then
  # filter out minio keys from EMPTY_SECRETS
  filtered=()
  for k in "${EMPTY_SECRETS[@]}"; do
    [[ "$k" == ".secrets.minio"* ]] || filtered+=("$k")
  done
  EMPTY_SECRETS=("${filtered[@]+${filtered[@]}}")
fi

# RS256-specific keys
if [[ "$JWT_ALG" == "RS256" ]]; then
  for k in ".secrets.jwtPrivateKey" ".secrets.jwtPublicKey"; do
    v=$(yq -r "$k // \"\"" "$TMP_CONFIG")
    if is_placeholder "$v"; then
      if [[ "$GENERATE_SECRETS" == true ]]; then
        KEY_DIR="$(mktemp -d)"
        openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out "$KEY_DIR/priv.pem" 2>/dev/null
        openssl rsa -in "$KEY_DIR/priv.pem" -pubout -out "$KEY_DIR/pub.pem" 2>/dev/null
        PRIV_B64=$(base64 -w0 < "$KEY_DIR/priv.pem" 2>/dev/null || base64 < "$KEY_DIR/priv.pem" | tr -d '\n')
        PUB_B64=$(base64 -w0 < "$KEY_DIR/pub.pem"  2>/dev/null || base64 < "$KEY_DIR/pub.pem"  | tr -d '\n')
        if [[ "$k" == ".secrets.jwtPrivateKey" ]]; then
          yq -i ".secrets.jwtPrivateKey = \"$PRIV_B64\"" "$TMP_CONFIG"
          info "  generated RSA keypair, filled .secrets.jwtPrivateKey"
        else
          yq -i ".secrets.jwtPublicKey  = \"$PUB_B64\""  "$TMP_CONFIG"
          info "  filled .secrets.jwtPublicKey"
        fi
      else
        EMPTY_SECRETS+=("$k (RS256 requires PEM keypair, base64-encoded)")
      fi
    fi
  done
fi

if [[ ${#EMPTY_SECRETS[@]} -gt 0 ]]; then
  err "The following secrets require values (use --generate-secrets for auto-generatable ones):
$(printf '  - %s\n' "${EMPTY_SECRETS[@]}")"
fi

# Strength check: JWT must be at least 32 chars if HS256
if [[ "$JWT_ALG" == "HS256" ]]; then
  JWT_V=$(yq -r ".secrets.jwtSecret" "$TMP_CONFIG")
  [[ ${#JWT_V} -ge 32 ]] || err ".secrets.jwtSecret must be ≥ 32 characters (current: ${#JWT_V}). Use 'openssl rand -hex 32'."
fi

# Block ultra-weak passwords
WEAK_RE='^(password|admin|123456|letmein|changeme|sia|test)$'
for k in ".secrets.adminPassword" ".secrets.mysqlPassword" ".secrets.redisPassword"; do
  v=$(yq -r "$k // \"\"" "$TMP_CONFIG")
  [[ -n "$v" ]] && echo "$v" | grep -iqE "$WEAK_RE" && err "$k contains an unsafe weak value"
done

ok "Secrets are present and meet strength requirements"

if [[ "$CHECK_ONLY" == true ]]; then
  info "Check-only mode; no files written."
  rm -f "$TMP_CONFIG"
  exit 0
fi

# -----------------------------------------------------------------------------
# Step 3: Render Helm values-prod.yaml (non-secret)
# -----------------------------------------------------------------------------
info "Rendering deploy/helm/sia/values-prod.yaml..."

VALUES_OUT="$PROJECT_ROOT/deploy/helm/sia/values-prod.yaml"

yq -n "
  global.imageRegistry = (load(\"$TMP_CONFIG\").registry.url) |
  global.imagePullSecrets = (
    (load(\"$TMP_CONFIG\").registry.pullSecret // \"\") as \$s |
    (if \$s == \"\" then [] else [\$s] end)
  ) |
  namespace = (load(\"$TMP_CONFIG\").cluster.namespace) |

  api.replicaCount          = (load(\"$TMP_CONFIG\").resources.api.replicas) |
  api.resources.requests    = (load(\"$TMP_CONFIG\").resources.api.requests) |
  api.resources.limits      = (load(\"$TMP_CONFIG\").resources.api.limits) |
  api.autoscaling.enabled   = (load(\"$TMP_CONFIG\").autoscaling.api.enabled) |
  api.autoscaling.minReplicas = (load(\"$TMP_CONFIG\").autoscaling.api.minReplicas) |
  api.autoscaling.maxReplicas = (load(\"$TMP_CONFIG\").autoscaling.api.maxReplicas) |
  api.autoscaling.targetCPU   = (load(\"$TMP_CONFIG\").autoscaling.api.targetCPUUtilizationPercentage) |

  consumer.replicaCount     = (load(\"$TMP_CONFIG\").resources.consumer.replicas) |
  consumer.resources.requests = (load(\"$TMP_CONFIG\").resources.consumer.requests) |
  consumer.resources.limits   = (load(\"$TMP_CONFIG\").resources.consumer.limits) |

  web.enabled               = true |
  web.replicaCount          = (load(\"$TMP_CONFIG\").resources.web.replicas) |
  web.resources.requests    = (load(\"$TMP_CONFIG\").resources.web.requests) |
  web.resources.limits      = (load(\"$TMP_CONFIG\").resources.web.limits) |

  ingress.enabled           = (load(\"$TMP_CONFIG\").ingress.enabled) |
  ingress.className         = (load(\"$TMP_CONFIG\").ingress.className) |
  ingress.host              = (load(\"$TMP_CONFIG\").ingress.host) |
  ingress.tls.enabled       = (load(\"$TMP_CONFIG\").ingress.tls.enabled) |
  ingress.tls.secretName    = (load(\"$TMP_CONFIG\").ingress.tls.secretName // \"sia-tls\") |
  ingress.annotations.\"cert-manager.io/cluster-issuer\" =
    (load(\"$TMP_CONFIG\").ingress.tls.clusterIssuer // \"\") |

  mysql.host                = (load(\"$TMP_CONFIG\").mysql.host) |
  mysql.port                = (load(\"$TMP_CONFIG\").mysql.port | tostring) |
  mysql.user                = (load(\"$TMP_CONFIG\").mysql.user) |
  mysql.database            = (load(\"$TMP_CONFIG\").mysql.database) |
  mysql.tls.mode            = (load(\"$TMP_CONFIG\").mysql.tls.mode) |
  mysql.tls.caPath          = (load(\"$TMP_CONFIG\").mysql.tls.caPath) |
  mysql.tls.caSecretName    = (load(\"$TMP_CONFIG\").mysql.tls.caSecretName // \"\") |

  redis.host                = (load(\"$TMP_CONFIG\").redis.host) |
  redis.port                = (load(\"$TMP_CONFIG\").redis.port | tostring) |
  redis.db                  = (load(\"$TMP_CONFIG\").redis.db | tostring) |
  redis.tls.enabled         = (load(\"$TMP_CONFIG\").redis.tls.enabled) |
  redis.tls.caPath          = (load(\"$TMP_CONFIG\").redis.tls.caPath) |
  redis.tls.caSecretName    = (load(\"$TMP_CONFIG\").redis.tls.caSecretName // \"\") |

  milvus.host               = (load(\"$TMP_CONFIG\").milvus.host) |
  milvus.port               = (load(\"$TMP_CONFIG\").milvus.port | tostring) |
  milvus.collectionName     = (load(\"$TMP_CONFIG\").milvus.collectionName) |

  minio.enabled             = (load(\"$TMP_CONFIG\").minio.enabled // false) |
  minio.host                = (load(\"$TMP_CONFIG\").minio.host // \"\") |
  minio.port                = ((load(\"$TMP_CONFIG\").minio.port // 9000) | tostring) |
  minio.bucket              = (load(\"$TMP_CONFIG\").minio.bucket // \"sia-reports\") |
  minio.secure              = (load(\"$TMP_CONFIG\").minio.secure // true) |

  network.httpsProxy        = (load(\"$TMP_CONFIG\").network.httpsProxy // \"\") |
  network.egressAllowedCidrs = (load(\"$TMP_CONFIG\").network.egressAllowedCidrs) |

  observability.otlpEndpoint = (load(\"$TMP_CONFIG\").observability.otlpEndpoint // \"\") |
  observability.logJsonFormat = (load(\"$TMP_CONFIG\").observability.logJsonFormat // true) |

  security.falcoRulesEnabled = (load(\"$TMP_CONFIG\").security.falcoRulesEnabled // false) |
  security.gatekeeperConstraintsEnabled = (load(\"$TMP_CONFIG\").security.gatekeeperConstraintsEnabled // false) |

  config.env                = \"production\" |
  config.logLevel           = \"INFO\" |
  config.jwtAlgorithm       = (load(\"$TMP_CONFIG\").secrets.jwtAlgorithm // \"HS256\") |

  jobs.migration.enabled    = (load(\"$TMP_CONFIG\").jobs.migration.enabled // true) |
  jobs.seed.enabled         = (load(\"$TMP_CONFIG\").jobs.seed.enabled // true)
" > "$VALUES_OUT"

ok "Wrote $VALUES_OUT"

# -----------------------------------------------------------------------------
# Step 4: Render K8s Secret manifest
# -----------------------------------------------------------------------------
info "Rendering K8s Secret manifest..."

RENDERED_DIR="$PROJECT_ROOT/deploy/rendered"
mkdir -p "$RENDERED_DIR"
chmod 700 "$RENDERED_DIR"

SECRET_OUT="$RENDERED_DIR/sia-secrets.yaml"
NS=$(yq -r ".cluster.namespace" "$TMP_CONFIG")

# base64 helper
b64() { printf '%s' "$1" | base64 | tr -d '\n'; }

{
  echo "# ==========================================================================="
  echo "# AUTO-GENERATED by configure.sh — DO NOT EDIT BY HAND, DO NOT COMMIT"
  echo "# Regenerate with: ./scripts/deploy/configure.sh --generate-secrets"
  echo "# ==========================================================================="
  echo "apiVersion: v1"
  echo "kind: Secret"
  echo "metadata:"
  echo "  name: sia-secrets"
  echo "  namespace: $NS"
  echo "type: Opaque"
  echo "data:"
  echo "  SIA_AUTH_JWT_SECRET: $(b64 "$(yq -r .secrets.jwtSecret "$TMP_CONFIG")")"
  echo "  SIA_AUTH_JWT_ALGORITHM: $(b64 "$(yq -r .secrets.jwtAlgorithm "$TMP_CONFIG")")"
  if [[ "$JWT_ALG" == "RS256" ]]; then
    echo "  SIA_AUTH_JWT_PRIVATE_KEY: $(yq -r .secrets.jwtPrivateKey "$TMP_CONFIG")"
    echo "  SIA_AUTH_JWT_PUBLIC_KEY:  $(yq -r .secrets.jwtPublicKey  "$TMP_CONFIG")"
  fi
  echo "  SIA_API_KEY: $(b64 "$(yq -r .secrets.apiKey "$TMP_CONFIG")")"
  echo "  SIA_ADMIN_PASSWORD: $(b64 "$(yq -r .secrets.adminPassword "$TMP_CONFIG")")"
  echo "  SIA_MYSQL_PASSWORD: $(b64 "$(yq -r .secrets.mysqlPassword "$TMP_CONFIG")")"
  REDIS_PASS=$(yq -r '.secrets.redisPassword // ""' "$TMP_CONFIG")
  echo "  SIA_REDIS_PASSWORD: $(b64 "$REDIS_PASS")"
  echo "  SIA_MINIO_ACCESS_KEY: $(b64 "$(yq -r '.secrets.minioAccessKey // ""' "$TMP_CONFIG")")"
  echo "  SIA_MINIO_SECRET_KEY: $(b64 "$(yq -r '.secrets.minioSecretKey // ""' "$TMP_CONFIG")")"
  MILVUS_TOK=$(yq -r '.secrets.milvusToken // ""' "$TMP_CONFIG")
  echo "  SIA_MILVUS_TOKEN: $(b64 "$MILVUS_TOK")"
  GOOGLE_K=$(yq -r '.secrets.googleApiKey // ""' "$TMP_CONFIG")
  echo "  SIA_GOOGLE_API_KEY: $(b64 "$GOOGLE_K")"
  ANTH_K=$(yq -r '.secrets.anthropicApiKey // ""' "$TMP_CONFIG")
  echo "  SIA_ANTHROPIC_API_KEY: $(b64 "$ANTH_K")"
  OPENAI_K=$(yq -r '.secrets.openaiApiKey // ""' "$TMP_CONFIG")
  echo "  SIA_OPENAI_API_KEY: $(b64 "$OPENAI_K")"
  HTTPS_PROXY_V=$(yq -r '.network.httpsProxy // ""' "$TMP_CONFIG")
  echo "  SIA_HTTPS_PROXY: $(b64 "$HTTPS_PROXY_V")"
} > "$SECRET_OUT"

chmod 600 "$SECRET_OUT"
ok "Wrote $SECRET_OUT  (mode 600)"

# -----------------------------------------------------------------------------
# Step 5: Write-back generated secrets to deployment.config.yaml if requested
# -----------------------------------------------------------------------------
if [[ "$GENERATE_SECRETS" == true ]]; then
  cp "$TMP_CONFIG" "$CONFIG_FILE"
  chmod 600 "$CONFIG_FILE"
  ok "Updated $CONFIG_FILE with generated secrets (mode 600)"
fi

rm -f "$TMP_CONFIG"

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Configuration complete${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "  Generated files:"
echo "    - $VALUES_OUT"
echo "    - $SECRET_OUT"
echo ""
echo "  Next step:"
echo "    ./scripts/deploy/deploy-k8s.sh"
echo ""
echo "  ${YELLOW}The secret manifest and deployment.config.yaml contain sensitive data.${NC}"
echo "  ${YELLOW}They are gitignored; never commit or paste them.${NC}"
echo ""
