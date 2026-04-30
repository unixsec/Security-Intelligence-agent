#!/usr/bin/env bash
# preflight_check.sh — production hardening verifier (SECURITY.md §11).
#
# Run from the repo root:
#   bash scripts/ops/preflight_check.sh
#
# Exits non-zero if any P0 hardening item is missing. Each check below
# corresponds to a hardening Task ID; the full Task index lives in the
# maintainer's local design/ directory (not in this repo on GitHub).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
WARN=0

ok()   { echo -e "\033[0;32m✓\033[0m $*"; PASS=$((PASS+1)); }
bad()  { echo -e "\033[0;31m✗\033[0m $*"; FAIL=$((FAIL+1)); }
warn() { echo -e "\033[1;33m!\033[0m $*"; WARN=$((WARN+1)); }

# 1. SEC-1: LDAP escape
if grep -q "escape_filter_chars" src/sia/auth/providers/ldap.py 2>/dev/null; then
  ok "SEC-1: LDAP filter escapes user input"
else
  bad "SEC-1: LDAP filter NOT escaped — see auth/providers/ldap.py"
fi

# 2. SEC-2: API key model exists
if [[ -f src/sia/models/api_key.py ]]; then
  ok "SEC-2: api_keys table model present"
else
  bad "SEC-2: api_keys model missing"
fi

# 3. SEC-3: PKCE
if grep -q "code_challenge_method" src/sia/auth/providers/oidc.py 2>/dev/null; then
  ok "SEC-3: OIDC PKCE wired up"
else
  bad "SEC-3: OIDC PKCE NOT wired"
fi

# 4. SEC-4: JWT revocation
if grep -q "is_token_revoked" src/sia/auth/jwt.py 2>/dev/null; then
  ok "SEC-4: JWT revocation in place"
else
  bad "SEC-4: JWT revocation missing"
fi

# 5. SEC-5: DNS timeout
if grep -q "_DNS_TIMEOUT_SEC" src/sia/collector/url_validator.py 2>/dev/null; then
  ok "SEC-5: DNS resolution has a timeout"
else
  bad "SEC-5: DNS timeout missing"
fi

# 6. DEP-1: ingress TLS default. Values file uses a nested ``tls.enabled`` two
#     keys deep below ``ingress``; awk-walk that section explicitly.
if awk '
  /^ingress:/ { in_ingress=1; next }
  in_ingress && /^[a-zA-Z]/ && !/^[ ]/ { in_ingress=0 }
  in_ingress && /^[[:space:]]*tls:/ { in_tls=1; next }
  in_tls && /enabled:[[:space:]]*true/ { found=1; exit }
  in_tls && /^[[:space:]]{0,2}[a-zA-Z]/ && !/^[[:space:]]{4,}/ { in_tls=0 }
  END { exit found ? 0 : 1 }
' deploy/helm/sia/values.yaml; then
  ok "DEP-1: ingress.tls.enabled=true (default)"
else
  bad "DEP-1: ingress.tls.enabled is not true by default"
fi

# 7. DEP-1: egress allow-list
if grep -A2 "egressAllowedCidrs:" deploy/helm/sia/values.yaml | grep -q "0.0.0.0/0"; then
  warn "DEP-1: egressAllowedCidrs still contains 0.0.0.0/0 — tighten in production overlay"
else
  ok "DEP-1: egressAllowedCidrs is restrictive"
fi

# 8. DEP-2: Gatekeeper applied automatically. The script paths the dir
#     into a variable, so we just need to see both the dir reference AND
#     a kubectl apply against it.
if grep -q "GATEKEEPER_DIR=" scripts/deploy/deploy-k8s.sh \
   && grep -q 'kubectl apply -f "\$GATEKEEPER_DIR' scripts/deploy/deploy-k8s.sh; then
  ok "DEP-2: deploy-k8s.sh applies Gatekeeper constraints"
else
  bad "DEP-2: Gatekeeper apply not in deploy-k8s.sh"
fi

# 9. DEP-4: alembic baseline migration present
if ls migrations/versions/*.py 2>/dev/null | grep -qv __init__.py; then
  ok "DEP-4: alembic versions populated"
else
  bad "DEP-4: migrations/versions/ is empty"
fi

# 10. CI: Trivy aquasecurity action
if grep -q "trivy-action" .github/workflows/ci.yml; then
  ok "CI: Trivy image scan in pipeline"
else
  bad "CI: Trivy image scan missing"
fi

# 11. CI: pip-audit blocking
if grep -E "pip-audit.*\|\| true" .github/workflows/ci.yml >/dev/null; then
  bad "TEST-2: pip-audit is non-blocking (\\|\\| true). Remove the suppression."
else
  ok "TEST-2: pip-audit blocks on known vulnerabilities"
fi

# 12. OBS-1: /metrics route mounted
if grep -q "make_asgi_app" src/sia/main.py; then
  ok "OBS-1: /metrics endpoint mounted"
else
  bad "OBS-1: /metrics endpoint missing"
fi

# 13. FN-1: scheduled report goes through exec_brief
if grep -q "build_brief" src/sia/scheduler/jobs.py; then
  ok "FN-1: scheduled report uses exec_brief pipeline"
else
  bad "FN-1: scheduled report still uses placeholder"
fi

echo ""
echo "Summary: ${PASS} passed, ${FAIL} failed, ${WARN} warnings"
[[ $FAIL -eq 0 ]] || exit 1
