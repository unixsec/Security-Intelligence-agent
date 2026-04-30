#!/usr/bin/env bash
# chaos_observe.sh — quick console for chaos drills.
# Watches: SIA pods, /metrics SLO ratios, open circuit breakers.
set -uo pipefail

NAMESPACE="${SIA_NAMESPACE:-sia}"

while true; do
  clear
  echo "=== SIA pods ($NAMESPACE) ==="
  kubectl get pods -n "$NAMESPACE" -o wide --no-headers | head -20
  echo
  echo "=== Probe failures (last 1m) ==="
  kubectl get events -n "$NAMESPACE" --field-selector type=Warning \
    --sort-by=.lastTimestamp | tail -10
  echo
  echo "=== Sample /metrics from sia-api ==="
  POD=$(kubectl get pod -n "$NAMESPACE" -l app.kubernetes.io/component=api -o name | head -1)
  if [[ -n "$POD" ]]; then
    kubectl exec -n "$NAMESPACE" "$POD" -c sia-api -- \
      sh -c "wget -qO- http://localhost:8080/metrics 2>/dev/null \
        | grep -E '^(sia_circuit_state|sia_stream_lag|sia_llm_call_total\{result=\"error\"\})' | head -10" \
      2>/dev/null || echo "(metrics unavailable)"
  fi
  echo
  echo "Refreshing in 10s; Ctrl-C to exit"
  sleep 10
done
