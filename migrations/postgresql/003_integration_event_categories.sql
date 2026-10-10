CREATE TABLE integration_event_categories (
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('usage', 'billing', 'subscription')),
    PRIMARY KEY (tenant_id, source, category),
    CONSTRAINT integration_event_categories_integration_fk
        FOREIGN KEY (tenant_id, source)
        REFERENCES integrations(tenant_id, source) ON DELETE CASCADE
);

-- Preserve the SQLite migration's observed-category backfill and safe default
-- for integrations with no event history.
INSERT INTO integration_event_categories(tenant_id, source, category)
SELECT DISTINCT i.tenant_id, i.source, ce.category
FROM integrations AS i
JOIN canonical_events AS ce ON ce.tenant_id = i.tenant_id AND ce.source = i.source
WHERE ce.category IN ('usage', 'billing', 'subscription')
ON CONFLICT (tenant_id, source, category) DO NOTHING;

INSERT INTO integration_event_categories(tenant_id, source, category)
SELECT i.tenant_id, i.source, 'usage'
FROM integrations AS i
WHERE NOT EXISTS (
    SELECT 1 FROM integration_event_categories AS granted
    WHERE granted.tenant_id = i.tenant_id AND granted.source = i.source
)
ON CONFLICT (tenant_id, source, category) DO NOTHING;
