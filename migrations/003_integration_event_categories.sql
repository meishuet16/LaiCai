CREATE TABLE integration_event_categories (
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('usage', 'billing', 'subscription')),
    PRIMARY KEY (tenant_id, source, category),
    FOREIGN KEY (tenant_id, source)
        REFERENCES integrations(tenant_id, source) ON DELETE CASCADE
);

-- Preserve only categories already observed for each legacy integration.
INSERT INTO integration_event_categories(tenant_id, source, category)
SELECT DISTINCT i.tenant_id, i.source, ce.category
FROM integrations i
JOIN canonical_events ce ON ce.tenant_id = i.tenant_id AND ce.source = i.source
WHERE ce.category IN ('usage', 'billing', 'subscription');

-- An unused integration has no category evidence; grant only the safe usage default.
INSERT INTO integration_event_categories(tenant_id, source, category)
SELECT i.tenant_id, i.source, 'usage'
FROM integrations i
WHERE NOT EXISTS (
    SELECT 1 FROM integration_event_categories g
    WHERE g.tenant_id = i.tenant_id AND g.source = i.source
);
