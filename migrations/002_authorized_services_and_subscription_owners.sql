CREATE TABLE service_principals (
    service_principal_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    token_digest TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('analyst', 'admin', 'operator')),
    authorized_sources_json TEXT NOT NULL,
    authorized_purposes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE TABLE subscription_owners (
    tenant_id TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, subscription_id),
    UNIQUE (tenant_id, subscription_id, customer_id),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);

INSERT INTO subscription_owners(tenant_id, subscription_id, customer_id)
SELECT tenant_id, subscription_id, MIN(customer_id)
FROM (
    SELECT tenant_id, subscription_id, customer_id FROM subscriptions
    UNION
    SELECT tenant_id, subscription_id, customer_id FROM subscription_events
    UNION
    SELECT tenant_id, subscription_id, customer_id FROM billing_events
    WHERE subscription_id IS NOT NULL
)
GROUP BY tenant_id, subscription_id;

CREATE TABLE subscription_events_v2 (
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
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, subscription_id, customer_id)
        REFERENCES subscription_owners(tenant_id, subscription_id, customer_id) ON DELETE CASCADE
);
INSERT INTO subscription_events_v2
SELECT tenant_id, event_id, subscription_id, customer_id, event_type, changed_fields_json, status, plan_id,
       started_at, current_period_end, ended_at, cancellation_requested_at, billing_interval,
       billing_interval_count, amount_minor, discount_minor, currency, occurred_at, received_at, source_available_at
FROM subscription_events;
DROP TABLE subscription_events;
ALTER TABLE subscription_events_v2 RENAME TO subscription_events;
CREATE INDEX subscription_events_history
    ON subscription_events(tenant_id, customer_id, subscription_id, occurred_at, received_at);

CREATE TABLE billing_events_v2 (
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
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, subscription_id, customer_id)
        REFERENCES subscription_owners(tenant_id, subscription_id, customer_id) ON DELETE CASCADE
);
INSERT INTO billing_events_v2
SELECT tenant_id, event_id, customer_id, subscription_id, event_type, payment_status, amount_minor, currency,
       occurred_at, received_at, source_available_at
FROM billing_events;
DROP TABLE billing_events;
ALTER TABLE billing_events_v2 RENAME TO billing_events;

CREATE TABLE subscriptions_v2 (
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
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, subscription_id, customer_id)
        REFERENCES subscription_owners(tenant_id, subscription_id, customer_id) ON DELETE CASCADE
);
INSERT INTO subscriptions_v2
SELECT tenant_id, subscription_id, customer_id, plan_id, status, started_at, current_period_end, ended_at,
       cancellation_requested_at, billing_interval, billing_interval_count, amount_minor, discount_minor,
       currency, updated_at
FROM subscriptions;
DROP TABLE subscriptions;
ALTER TABLE subscriptions_v2 RENAME TO subscriptions;
CREATE INDEX subscriptions_account ON subscriptions(tenant_id, customer_id, status);
