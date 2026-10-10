我建议 4 个 Member 各自负责一个 Workstream，但不完全等于 Part 1、2、3、4 各分一个人。

因为 Part 4 依赖前面三个部分。如果照章节顺序开发，负责 Part 4 的人可能需要一直等别人。

更合理的方式是：四个人从第一天同时开发，用统一 API Contract 和 Mock Data 连接，最后整合。

## 四人工作分配

Member 1 — Data & Backend Engineer

Part 1

负责数据来源、数据库、安全和数据接入。

- PostgreSQL Database Schema
- Historical Dataset Import
- Push API、Customer Identity Mapping
- Usage / Billing / Subscription Normalization
- MRR Calculation、Tenant Security

交付： 可用的数据库、真实数据接入 API、历史事件回放输入。

Member 2 — AI / ML Engineer

Part 2 + Learning

负责预测模型及后续模型改善。

- Personalized Behavioural Features
- 7/14/30-Day LightGBM Prediction
- Calibration、SHAP、Reliability Gate
- Baseline Comparison、Historical Evaluation
- Part 4 Model Feedback Evaluation & Controlled Retraining

交付： 可复现的训练流程、真实模型预测 API、性能报告、模型版本与更新验证。

Member 3 — Decision Engine Engineer

Part 3

负责把预测转化成可以执行、可以审核的商业决策。

- Risk & Confidence Routing
- Revenue Exposure、Top-K Prioritization
- Next Best Action Rule Engine
- Budget / Staff Capacity
- Break-even & ROI Calculation
- Human Approval、Action & Outcome Tracking

交付： Decision API、预算及 ROI 计算、完整人工决定与行动追踪流程。

Member 4 — Frontend & Product Integration

Part 4 UI

负责完整 Dashboard、用户体验及端到端 Demo。

- Integration Status Dashboard
- Prediction Radar、Customer Profile
- Retention Strategy Lab UI
- Business Analytics Dashboard
- Customer Timeline
- Outcome Feedback Display
- End-to-End Replay Demo UI

交付： 可以让 Judge 实际操作的 RetainIQ Web App。

## 为什么这样分可以同时做？

四个人开发时，先使用同一份约定好的 Mock API。

Member 1

Data API

Member 2

Prediction API

Member 3

Decision API

Member 4

Frontend / Dashboard

Shared API Contracts + Mock Data

每个人根据同一套字段开发，不必等待真实模型或其他模块全部完成。

例如 Member 3 不需要等 Member 2 训练好 LightGBM。

Member 3 可以先用这样的测试输入开发：

```
{
  "customer_id": "cust_001",
  "p_churn_7d": 0.12,
  "p_churn_14d": 0.38,
  "p_churn_30d": 0.81,
  "reliability": {
    "status": "sufficient_evidence"
  }
}
```

Member 4 也可以提前使用 Mock API 开发 Dashboard。

注意：Mock Data 只能用来开发和测试，不可以当成真实模型表现给 Judge。

## 开发开始前，四个人先共同确定这五件事

| 要确认的事项                                    | 主要负责人         |
| ----------------------------------------- | ------------- |
| 真实历史数据是否足够支持 7/14/30 天预测                  | Member 1 + 2  |
| PostgreSQL Schema、Customer ID、Tenant ID   | Member 1      |
| Prediction JSON Contract + Reliability 字段 | Member 2      |
| Decision API、Action Status、Outcome 字段     | Member 3      |
| 共同 API Types、Mock Fixtures、页面调用方式         | Member 4 + 全员 |

这一步可以作为 Day 0 — Integration Contract Freeze。

尤其要明确 `prediction_id` 与 `prediction_run_id` 不是同一个东西，而且 `as_of` 和 `occurred_at` 不能混用。

## 建议 Repo 结构

```
retainiq/
├── backend/
│   ├── data/                 # Member 1
│   ├── ingestion/            # Member 1
│   ├── database/             # Member 1
│   ├── prediction/           # Member 2
│   ├── decision/             # Member 3
│   └── feedback/             # Member 2 + 4, clearly split
│
├── frontend/                 # Member 4
│   ├── dashboard/
│   ├── predictions/
│   ├── strategy-lab/
│   └── customer-timeline/
│
├── shared/
│   ├── contracts/
│   └── fixtures/
│
├── tests/
├── docs/
├── RetainIQ_v2_Complete_Requirements.md
├── TEAM_LOG.md
└── AGENTS.md
```

Member 2 负责 Feedback 的标签核对、模型评估和重新训练逻辑；Member 4 负责反馈结果的读取与展示，不重复实现 ML。

## GitHub 协作规则

每人从独立 Branch 开发，避免一直修改同一份代码。

| Member   | Branch                       |
| -------- | ---------------------------- |
| Member 1 | `feature/data-foundation`    |
| Member 2 | `feature/prediction-engine`  |
| Member 3 | `feature/decision-engine`    |
| Member 4 | `feature/frontend-dashboard` |

每个 commit 必须同步更新 `TEAM_LOG.md`，描述具体改动、测试结果和下一步。合并时保留所有人的日志记录。

跨模块 Contract 修改必须先通知受影响成员，不能自己随意改 JSON 字段和数据库结构。

## 开发优先顺序

虽然四人并行，但每个人内部应这样安排：

| Member | 第一阶段                | 第二阶段                     | 最后阶段                       |
| ------ | ------------------- | ------------------------ | -------------------------- |
| 1      | Dataset + Schema    | Push API + Normalization | Security + Replay          |
| 2      | Features + Baseline | LightGBM + Calibration   | Evaluation + Learning Gate |
| 3      | Routing + Ranking   | Action Rules + ROI       | Human Approval + Outcome   |
| 4      | Layout + Mock UI    | Dashboard + Strategy Lab | Timeline + Full Demo       |

所有人都要负责自己模块的单元测试；最终端到端整合和验收由四人共同负责，Member 4 负责组织 Demo 流程，不是独自承担所有 Integration Bugs。

### 我最担心的两件事

1\. Member 1 / Member 2 是最大技术风险。 如果找不到有时间戳、真实流失日期和足够历史行为的 Dataset，整套 Multi-Horizon Prediction 就无法被严谨验证。因此两个人必须最早确认数据可行性。

2\. Member 4 不能最后才拿到 API。 要从第一天提供约定的 API Response 和 Mock Fixtures，否则漂亮 Dashboard 很可能和真正的 Backend 无法连接。

## 最终建议

四个人的分配就这样定：

- Member 1：Data Foundation + Core Backend
- Member 2：Prediction Engine + Model Learning
- Member 3：Decision Engine + Human Workflow
- Member 4：Frontend + Analytics Dashboard + Demo Experience

这比简单按 Part 1–4 分组更合理，因为 Part 4 的模型学习由 ML 负责人处理，Dashboard 则由 Frontend 负责人处理。

最终目标：四个人同时开发四个模块，但最后交付的是一个完整 RetainIQ 系统，而不是四个独立 Demo。