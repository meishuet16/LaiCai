# Hybrid dataset strategy

RetainIQ keeps two independent evidence tracks. Synthetic data supports engineering and synthetic model development. It does not replace the real-data or real-world validation gate.

| Property | Synthetic SaaS v1.2 | Real KKBox research |
|---|---|---|
| Dataset identity | `synthetic_saas_v1_2`, immutable `synthetic-saas-v1-2-*` dataset IDs | `real_kkbox`, if separately authorized and acquired |
| Local artifacts | `C:\Users\User\RetainIQ-private\synthetic_saas_v1_2`; separate SQLite DB per dataset ID | None acquired; no database or imported rows |
| Target | Simulated account-level loss of final paid entitlement; positive within 7/14/30 days | Unvalidated for this project's required effective-churn and observation contract |
| Current status | QUICK/STANDARD/FULL generated and validated; STANDARD/FULL canonical imports verified; Member 2 read smoke passed | `NOT_VALIDATED`; acquisition and terms remain a separate gate |
| Permitted conclusion | Synthetic integration and training experiments only | No conclusion until authorized source and labels are verified |

Keep dataset IDs, tenants, storage, target policy, features, fitted model provenance, calibration, reports, dashboard provenance, and readiness states separate. Never pool rows, combine metrics, pass a synthetic label as real, or use synthetic model evidence to claim performance on real customers. The synthetic adapter identifies each dataset in the local database and verifies that identity before import/replay. The shared database schema is versioned but each dataset has its own database file.

[`DATASET_CARD.md`](../DATASET_CARD.md) remains authoritative for the real-data decision. The generator neither reads nor modifies KKBox files. See [`SYNTHETIC_SAAS_DATASET.md`](SYNTHETIC_SAAS_DATASET.md) for generated artifacts and [`MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`](MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md) for the synthetic integration contract.
