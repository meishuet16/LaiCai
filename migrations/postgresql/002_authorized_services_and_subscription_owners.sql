CREATE TABLE service_principals (
    service_principal_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    token_digest TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('analyst', 'admin', 'operator')),
    authorized_sources_json TEXT NOT NULL,
    authorized_purposes_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT service_principals_tenant_fk
        FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE TABLE subscription_owners (
    tenant_id TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, subscription_id),
    CONSTRAINT subscription_owners_identity_uq UNIQUE (tenant_id, subscription_id, customer_id),
    CONSTRAINT subscription_owners_customer_fk
        FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE
);

-- Inserting distinct owners preserves the SQLite migration's refusal to guess
-- when the same tenant subscription appears under multiple customers.
INSERT INTO subscription_owners(tenant_id, subscription_id, customer_id)
SELECT tenant_id, subscription_id, customer_id
FROM (
    SELECT tenant_id, subscription_id, customer_id FROM subscriptions
    UNION
    SELECT tenant_id, subscription_id, customer_id FROM subscription_events
    UNION
    SELECT tenant_id, subscription_id, customer_id FROM billing_events
    WHERE subscription_id IS NOT NULL
) AS discovered_owners;

ALTER TABLE subscription_events
    ADD CONSTRAINT subscription_events_owner_fk
    FOREIGN KEY (tenant_id, subscription_id, customer_id)
    REFERENCES subscription_owners(tenant_id, subscription_id, customer_id) ON DELETE CASCADE;

ALTER TABLE billing_events
    ADD CONSTRAINT billing_events_owner_fk
    FOREIGN KEY (tenant_id, subscription_id, customer_id)
    REFERENCES subscription_owners(tenant_id, subscription_id, customer_id) ON DELETE CASCADE;

ALTER TABLE subscriptions
    ADD CONSTRAINT subscriptions_owner_fk
    FOREIGN KEY (tenant_id, subscription_id, customer_id)
    REFERENCES subscription_owners(tenant_id, subscription_id, customer_id) ON DELETE CASCADE;
