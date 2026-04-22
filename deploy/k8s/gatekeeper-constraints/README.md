# OPA Gatekeeper Constraints — SEC-012

Sample policies that harden any cluster running SIA. **Prerequisite:**
Gatekeeper must be installed in the cluster
(see <https://open-policy-agent.github.io/gatekeeper/>).

Apply in order:

```bash
# 1. Install ConstraintTemplates (one-time per cluster)
kubectl apply -f template-read-only-root.yaml
kubectl apply -f template-required-resources.yaml
kubectl apply -f template-block-latest-tag.yaml

# 2. Apply constraints that use those templates
kubectl apply -f constraint-sia-readonly-root.yaml
kubectl apply -f constraint-sia-required-resources.yaml
kubectl apply -f constraint-sia-block-latest-tag.yaml
```

Each constraint is scoped to `namespace=sia` by default. Widen as needed.

## What they enforce

| File | Enforces |
|---|---|
| `template-read-only-root.yaml` | Every container in the target ns has `securityContext.readOnlyRootFilesystem: true` |
| `template-required-resources.yaml` | Every container declares both `requests` and `limits` for CPU + memory |
| `template-block-latest-tag.yaml` | No container uses `:latest` or missing tag |

Violations are logged to the Gatekeeper audit log and can be set to `enforcementAction: deny` (blocking) after a soak period.
