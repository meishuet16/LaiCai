# RetainIQ v2 dataset card

**Real-data readiness: `NOT_READY`**
**Synthetic SaaS v1.2 readiness: `READY_FOR_SYNTHETIC_MODEL_DEVELOPMENT`**
**Assessment date:** 2026-10-10
**Selected real dataset:** None
**Real records imported:** 0

## Decision

No real dataset currently available to this project is both authorized for this use and verified to support the canonical subscription-churn target. No real source file was imported. Actual real account/event counts, event date ranges, subscription coverage, observation completeness, and 7/14/30-day label counts are **not measured**. The separately generated Synthetic SaaS v1.2 family is ready for synthetic development only; it does not change this real-data decision.

The closest technical candidate was KKBox's WSDM churn competition. Its public challenge describes dated membership transactions and usage logs and asks for a churn outcome around subscription expiration. Its rules limit use to competition participation, forum participation, academic research, and education; access is under the competition terms and redistribution to nonparticipants is barred. We did not accept terms, obtain a participant-authorized download, or verify that this Dormathon project and downstream handoff fit the permitted purpose. It is therefore **not selected or authorized for import**. See the [official challenge](https://www.kaggle.com/c/kkbox-churn-prediction-challenge), [competition rules](https://www.kaggle.com/c/kkbox-churn-prediction-challenge/rules), and [WSDM task description](https://www.wsdm-conference.org/2018/call-for-participants.html).

## Candidate review

| Candidate | Provenance / permission evidence | Longitudinal and target fit | Decision |
|---|---|---|---|
| KKBox WSDM churn competition | Official Kaggle competition and rules; participant access and restricted use terms. No terms accepted or files acquired. | Closest fit: member IDs, dated transactions and usage logs, subscription expiration context, and a competition churn target tied to renewal within 30 days. Per-row original availability, stable subscription IDs, effective entitlement termination, fully observed 7/14/30-day outcomes, and repeated-cutoff coverage have not been verified from acquired files. | Technically promising, but not project-authorized or measured; not imported. |
| UCI Iranian Churn | [UCI record](https://archive.ics.uci.edu/dataset/563/iranian%2Bchurn%2Bdataset) describes a static churn dataset and CC BY 4.0. | Customer-level features and a later churn state; no dated event ledger or effective termination timestamp suitable for repeated as-of snapshots. | Disqualified for early-warning replay. |
| IBM Telco Customer Churn | [IBM sample repository](https://github.com/IBM/telco-customer-churn-on-icp4d) was reviewed. | Static customer attributes with a churn class; no dated event history or source availability timeline. | Disqualified for early-warning replay. |
| UCI Online Retail II | [UCI record](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii) identifies dated retail transactions and CC BY 4.0. | Invoice dates and customer identifiers do not establish a paid subscription, entitlement lifecycle, or churn-effective date. Retail inactivity is not subscription churn. | Disqualified for target semantics. |
| COFINFAD | [Mendeley record](https://data.mendeley.com/datasets/mhb4zn3258/1) describes banking transactions and lists CC BY 4.0. | Financial transactions are not subscription or paid-entitlement records; no verified subscription end or churn-effective outcome for this contract. | Disqualified for target semantics and domain. |
| SaaS practice datasets | [SQLShed](https://sqlshed.com/practice-datasets/saas-subscriptions/) labels its generated data synthetic; other educational datasets reviewed are also generated/static. | May contain generated subscriptions/events, but are not genuine customer histories or real outcome evidence. | Fixture-only; cannot clear the real-data gate. |

## Per-candidate feasibility checks

Counts below are deliberately recorded as **not measured**: no candidate files were authorized and inspected locally. Published schema descriptions are source-document evidence, not measurements from acquired files.

| Candidate | Verified account/event counts and date ranges | Stable account/subscription identity | Lifecycle, outcomes and known cancellations | Usage/billing coverage and availability | 7/14/30, censoring, chronology and repeated cutoffs |
|---|---|---|---|---|---|
| KKBox WSDM | Not measured. Official challenge describes dated transaction and user-log data; local row counts/ranges unavailable. | A member identifier is described; a canonical stable subscription ID and account-to-subscription mapping were not verified. | The target concerns renewal within 30 days of subscription expiry. Source-backed effective entitlement-loss time, pending-cancellation exclusion, and per-row observation coverage were not verified. | Transaction and usage sources are described; local completeness and original first-available times were not verified. | The 30-day challenge target does not establish genuine 7/14/30 labels or exact churn-effective time. Mature follow-up, censoring, repeated cutoffs, and separate train/development/calibration/untouched-test windows were not verified from files. |
| UCI Iranian Churn | Not measured from files. The published record describes customer rows, not an event stream. | Customer-row identity only; no subscription identity. | Static later churn state; no effective cancellation/end timestamp or known-cancellation-at-cutoff field. | Aggregated customer features; no dated usage/billing event coverage or per-event availability. | Cannot form verified event-based 7/14/30 outcomes, censoring checks, or repeated temporal cutoffs from the published static schema. |
| IBM Telco Customer Churn | Not measured from files. The reviewed source is a static customer table. | Customer-row identity only; no subscription identity. | Static churn class; no effective end time or known-cancellation-at-cutoff state. | Snapshot attributes; no dated usage/billing history or source-availability timeline. | No genuine 7/14/30 label timing, censoring, chronological replay, or repeated cutoffs. |
| UCI Online Retail II | Not measured from files. The source describes dated invoices; local event counts/ranges were not computed. | Invoice customer identifier where populated; no subscription identity or paid-entitlement mapping. | Retail purchase/cancellation invoices do not establish a subscription lifecycle or effective churn. | Dated retail purchases/refunds are not subscription usage/billing coverage; original source availability was not verified. | No valid subscription churn horizons or entitlement observation/censoring policy; repeated invoice dates do not establish valid subscription cutoffs. |
| COFINFAD | Not measured from files. The Mendeley record describes banking transactions; record metadata is not a local coverage check. | Banking customer identifier is described; subscription identity is not established. | No verified subscription lifecycle or churn-effective outcome for this target. | Banking transaction dates are outside subscription billing/usage semantics; original availability was not verified. | No verified 7/14/30 subscription outcomes, censoring policy, or subscription-based temporal splits. |
| Synthetic SaaS practice data | Not a real-data candidate; no files imported or measured here. | Generated IDs may be internally stable but do not establish genuine customer identity. | Generated lifecycle labels/events are synthetic. | Generated usage and invoice streams are synthetic; no real-source availability semantics. | May exercise mechanics only; cannot establish real horizons, mature outcomes, or predictive evaluation. |

## Acquisition attempt and access boundary

- Reviewed the official KKBox challenge, rules, and WSDM task description in browser research.
- Checked local availability with `Get-Command kaggle -ErrorAction SilentlyContinue` and `python -c "import importlib.util; print(bool(importlib.util.find_spec('kaggle')))"`; neither a Kaggle executable nor Python package is installed.
- No raw download was attempted: there is no local participant-authorized Kaggle client, the rules require access under accepted competition terms, and we cannot accept those terms or infer that this project's use is permitted. No third-party mirror was used to bypass the restriction.
- Repository scan found no historical customer-data export. Real records imported: **0**. Candidate file counts and measured coverage: **not available**.

If the project owner later confirms eligibility and a participant independently accepts the official terms, the official client acquisition command is:

```powershell
kaggle competitions download -c kkbox-churn-prediction-challenge -p .\data\source\kkbox
```

This is a gated future instruction; it was **not run**, and it does not establish permission. Keep authorized source files within the terms and outside Git. The challenge's multi-file source has no reviewed adapter in this repository; do not ingest a target column as an event or silently interpret cancellation flags as effective churn.

## Predictive-data feasibility

| Required check | Evidence/status |
|---|---|
| Verified account count, event count and source date ranges | Not measured: no authorized source files acquired. Real imported accounts/events: 0. |
| Stable account-to-subscription mapping | Not verified for any acquired candidate. The canonical store requires explicit tenant/source/account mapping and subscription identifiers. |
| Subscription/churn-effective dates | No local source evidence. A prediction target or cancellation request is not itself an effective paid-entitlement termination. |
| Usage and billing coverage | Not measured for real records. Synthetic fixtures exercise these event pathways only. |
| Known-cancellation exclusion | Implemented at account snapshot level; no real population coverage measured. |
| Right censoring and complete observation | Not measured. No real observation-through date is available. |
| 7/14/30-day labels | **Unsupported as genuine labels.** Storage accepts all three horizons, but there is no label builder and no verified outcomes/observation windows. |
| Chronological train/development/calibration/test windows | Not assessable without dates, enough mature outcomes, and a frozen source policy. No split counts computed. |
| Repeated account cutoffs | Not measured for an authorized source. The as-of API can query repeated cutoffs if events and original availability are present. |
| Original per-record availability timestamps | Not verified for an acquired source. Import defaults to actual `received_at`; this does not prove earlier historical availability. |

## Local evidence and limitations

`python -m examples.member2_as_of_history` remains a small API fixture. Separately, Synthetic SaaS v1.2 QUICK, STANDARD, and FULL artifacts passed validation; STANDARD and FULL passed isolated canonical import and Member 2 read-only smoke checks. The v1.2 handoff includes synthetic horizon and chronological evidence. This is synthetic integration and training readiness only; no model has been trained and it does not establish real-data integration, real-world validation, or model performance on real customers. See [`docs/SYNTHETIC_SAAS_DATASET.md`](docs/SYNTHETIC_SAAS_DATASET.md) and [`docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md`](docs/MEMBER1_TO_MEMBER2_SYNTHETIC_HANDOFF.md).

The implementation stores event occurrence, receipt, and optional verified source-availability times; as-of visibility requires both occurrence and availability to be no later than the cutoff. It reconstructs subscription state from append-only events. The database is SQLite, not the PostgreSQL storage required by the integrated production requirements. There is no acquired historical dataset, source-specific mapping, or training pipeline.

**Next gate:** obtain explicit project authorization for a legitimate historical source; acquire it through the source's permitted method; inspect schema and terms; then measure account, subscription, event, availability, and observation coverage before writing an adapter or declaring any horizon feasible.
