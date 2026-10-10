CREATE TABLE dataset_identity (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    dataset_id TEXT NOT NULL UNIQUE,
    dataset_version TEXT NOT NULL,
    dataset_type TEXT NOT NULL CHECK (dataset_type = 'synthetic_saas'),
    target_policy_version TEXT NOT NULL,
    generator_version TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    bound_at TEXT NOT NULL
);
CREATE TABLE observation_coverage (
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,
    coverage_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    source_category TEXT NOT NULL CHECK (source_category IN ('usage', 'billing', 'subscription')),
    covered_from TEXT NOT NULL,
    covered_through TEXT NOT NULL,
    coverage_status TEXT NOT NULL CHECK (coverage_status IN (
        'complete', 'partial', 'outage', 'delayed', 'missing_historical_backfill',
        'not_created', 'entitlement_ended', 'censored'
    )),
    coverage_completeness REAL NOT NULL CHECK (coverage_completeness >= 0 AND coverage_completeness <= 1),
    coverage_available_at TEXT NOT NULL,
    observation_policy_version TEXT NOT NULL,
    normalized_payload_sha256 TEXT NOT NULL,
    PRIMARY KEY (tenant_id, source, coverage_id),
    FOREIGN KEY (tenant_id, customer_id)
        REFERENCES customers(tenant_id, customer_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, source, source_category)
        REFERENCES integration_event_categories(tenant_id, source, category) ON DELETE CASCADE,
    CHECK (covered_from < covered_through)
);
CREATE INDEX observation_coverage_as_of
    ON observation_coverage(tenant_id, customer_id, source, coverage_available_at, covered_from, covered_through);

CREATE TABLE synthetic_import_checkpoints (
    dataset_id TEXT NOT NULL,
    stream_name TEXT NOT NULL,
    last_row_number INTEGER NOT NULL CHECK (last_row_number >= 0),
    accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
    duplicate_count INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_count >= 0),
    rejected_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (dataset_id, stream_name),
    FOREIGN KEY (dataset_id) REFERENCES dataset_identity(dataset_id) ON DELETE CASCADE
);
