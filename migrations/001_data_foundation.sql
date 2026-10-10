CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY
);

CREATE TABLE integrations (
    integration_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    token_digest TEXT NOT NULL UNIQUE,
    authorized_purposes_json TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_successful_ingestion_at TEXT,
    last_failure_at TEXT,
    last_failure_code TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    UNIQUE (tenant_id, source)
);

CREATE TABLE customers (
    tenant_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    account_status TEXT NOT NULL DEFAULT 'active'
        CHECK (account_status IN ('active', 'inactive')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, customer_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE TABLE customer_identities (
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    external_customer_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, source, external_customer_id),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);

CREATE TABLE canonical_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('usage', 'billing', 'subscription')),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source_available_at TEXT,
    schema_version TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    normalized_payload_sha256 TEXT NOT NULL,
    UNIQUE (tenant_id, source, source_event_id),
    UNIQUE (tenant_id, event_id),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);
CREATE INDEX canonical_events_account_time
    ON canonical_events(tenant_id, customer_id, occurred_at, received_at);
CREATE INDEX canonical_events_availability
    ON canonical_events(tenant_id, customer_id, source_available_at, received_at);

CREATE TABLE usage_events (
    tenant_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    customer_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    feature TEXT,
    quantity INTEGER,
    unit TEXT,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source_available_at TEXT,
    PRIMARY KEY (tenant_id, event_id),
    FOREIGN KEY (tenant_id, event_id)
        REFERENCES canonical_events(tenant_id, event_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);

CREATE TABLE billing_events (
    tenant_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    customer_id TEXT NOT NULL,
    subscription_id TEXT,
    event_type TEXT NOT NULL,
    payment_status TEXT NOT NULL CHECK (payment_status IN ('failed', 'succeeded')),
    amount_minor INTEGER,
    currency TEXT,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source_available_at TEXT,
    PRIMARY KEY (tenant_id, event_id),
    FOREIGN KEY (tenant_id, event_id)
        REFERENCES canonical_events(tenant_id, event_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);

CREATE TABLE subscriptions (
    tenant_id TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    plan_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('trialing', 'active', 'past_due', 'pending_cancel', 'ended')),
    started_at TEXT,
    current_period_end TEXT,
    ended_at TEXT,
    cancellation_requested_at TEXT,
    billing_interval TEXT CHECK (billing_interval IN ('day', 'week', 'month', 'quarter', 'year')),
    billing_interval_count INTEGER CHECK (billing_interval_count IS NULL OR billing_interval_count > 0),
    amount_minor INTEGER CHECK (amount_minor IS NULL OR amount_minor >= 0),
    discount_minor INTEGER CHECK (discount_minor IS NULL OR discount_minor >= 0),
    currency TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, subscription_id),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);
CREATE INDEX subscriptions_account ON subscriptions(tenant_id, customer_id, status);

CREATE TABLE subscription_events (
    tenant_id TEXT NOT NULL,
    event_id INTEGER NOT NULL,
    subscription_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    changed_fields_json TEXT NOT NULL,
    status TEXT,
    plan_id TEXT,
    started_at TEXT,
    current_period_end TEXT,
    ended_at TEXT,
    cancellation_requested_at TEXT,
    billing_interval TEXT,
    billing_interval_count INTEGER,
    amount_minor INTEGER,
    discount_minor INTEGER,
    currency TEXT,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source_available_at TEXT,
    PRIMARY KEY (tenant_id, event_id),
    FOREIGN KEY (tenant_id, event_id)
        REFERENCES canonical_events(tenant_id, event_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);
CREATE INDEX subscription_events_history
    ON subscription_events(tenant_id, customer_id, subscription_id, occurred_at, received_at);

CREATE TABLE feature_snapshots (
    feature_snapshot_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    data_cutoff_at TEXT NOT NULL,
    features_json TEXT NOT NULL,
    data_quality_status TEXT NOT NULL,
    UNIQUE (tenant_id, customer_id, as_of, feature_version),
    UNIQUE (tenant_id, feature_snapshot_id),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);

CREATE TABLE churn_labels (
    tenant_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    horizon_days INTEGER NOT NULL CHECK (horizon_days IN (7, 14, 30)),
    label TEXT NOT NULL CHECK (label IN ('0', '1', 'unknown')),
    churn_type TEXT,
    outcome_at TEXT,
    label_observed_through TEXT NOT NULL,
    label_policy_version TEXT NOT NULL,
    PRIMARY KEY (tenant_id, customer_id, as_of, horizon_days, label_policy_version),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);

CREATE TABLE predictions (
    tenant_id TEXT NOT NULL,
    prediction_id TEXT NOT NULL,
    prediction_run_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('scored', 'abstained', 'known_cancellation', 'not_eligible')),
    p_churn_7d REAL,
    p_churn_14d REAL,
    p_churn_30d REAL,
    feature_snapshot_id TEXT,
    feature_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    calibration_version TEXT NOT NULL,
    label_policy_version TEXT,
    reliability_status TEXT NOT NULL CHECK (reliability_status IN ('sufficient_evidence', 'limited_evidence', 'insufficient_evidence')),
    reliability_reasons_json TEXT NOT NULL,
    data_freshness_status TEXT NOT NULL CHECK (data_freshness_status IN ('fresh', 'partially_stale', 'stale', 'unknown')),
    input_data_as_of TEXT,
    uncertainty_status TEXT NOT NULL DEFAULT 'not_quantified' CHECK (uncertainty_status = 'not_quantified'),
    explanations_by_horizon_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, prediction_id),
    UNIQUE (tenant_id, customer_id, as_of),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, feature_snapshot_id)
        REFERENCES feature_snapshots(tenant_id, feature_snapshot_id),
    CHECK (
        (status = 'scored' AND p_churn_7d IS NOT NULL AND p_churn_14d IS NOT NULL
            AND p_churn_30d IS NOT NULL AND p_churn_7d >= 0 AND p_churn_14d >= p_churn_7d
            AND p_churn_30d >= p_churn_14d AND p_churn_30d <= 1)
        OR
        (status <> 'scored' AND p_churn_7d IS NULL AND p_churn_14d IS NULL AND p_churn_30d IS NULL)
    )
);

CREATE INDEX predictions_run ON predictions(tenant_id, prediction_run_id);
