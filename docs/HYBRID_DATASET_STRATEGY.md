# Hybrid dataset strategy

RetainIQ has two independent evidence tracks.

| Property | Synthetic SaaS | Real KKBox research |
|---|---|---|
| Dataset type | `synthetic_saas` | `real_kkbox` |
| Operational demo | Primary | No |
| Canonical 7/14/30 effective churn | Simulated lifecycle supports future materialization | Not validated |
| Training/evaluation population | Synthetic only | Separate research only |
| Current readiness | Generator and import evidence determine status | `NOT_SUITABLE_FOR_REQUIRED_TARGET` |

Dataset IDs, tenant/source namespaces, target policies, splits, feature outputs, fitted artifacts, calibration, reports, dashboard provenance, and readiness states must remain separate. Never pool rows, publish a combined metric, treat target definitions as equivalent, or claim KKBox validates synthetic model performance.

`DATASET_CARD.md` remains the authoritative real-data gate. This generator does not read, modify, copy, or adapt KKBox files.
