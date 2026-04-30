# Chaos Mesh Experiments — SIA Resilience Suite (v0.4-7)

Six pre-built experiments under `deploy/chaos/experiments/`. Each one targets
a specific failure mode from the maintainer-local FMEA (in `design/`,
not committed to GitHub) and tests that the controls described there
actually hold.

## Prerequisites

- [Chaos Mesh operator](https://chaos-mesh.org/docs/quick-start/) installed in `chaos-testing`.
- SIA already deployed in `sia` namespace.
- A side terminal running `bash scripts/ops/chaos_observe.sh` (provided) to
  watch alerts and SLO burn.

## Suite

| File | Targets | Hypothesis | Expected outcome |
|---|---|---|---|
| `01-kill-api-pod.yaml` | one `sia-api` pod | k8s rescheduling + PDB minAvailable=1 prevent outage | Service stays 200 OK; rollout reschedules within 15s |
| `02-redis-network-loss.yaml` | egress to redis | rate limiter falls back to local; stream consumer pauses | Login still works (degraded RL); analyzer pauses, no DLQ |
| `03-mysql-stall.yaml` | mysql IO delay 5s | API request budget burns; readiness probe fails one pod | HPA does NOT panic-scale; SLO alert fires after 10 min |
| `04-llm-provider-5xx.yaml` | network partition to anthropic.com | circuit breaker opens; failover to next provider | `sia_circuit_state{name="anthropic"}=2` for 5 min; classify_intel still succeeds |
| `05-clock-skew-consumer.yaml` | +90s skew on consumer | tz-aware datetimes (SEC-7) keep CB intact | No spurious "circuit half-open never closes" |
| `06-pod-cpu-stress.yaml` | sia-consumer CPU 95% | HPA scales out within ~2 min | New replica picks up `xreadgroup`; lag drops |

## Run

```bash
# One at a time — chain only after previous reverts cleanly.
kubectl apply -f deploy/chaos/experiments/01-kill-api-pod.yaml
kubectl get podchaos -n chaos-testing
# Watch:
bash scripts/ops/chaos_observe.sh
```

Cleanup:

```bash
kubectl delete -f deploy/chaos/experiments/
```

## Reporting

Every quarter run the full suite, paste the Grafana screenshots into a
quarterly chaos report kept in the maintainer's local `design/` directory
(not in git), and update the local FMEA there if any alert / behaviour
deviated from the hypothesis.
