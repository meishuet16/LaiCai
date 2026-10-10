CREATE TABLE service_principal_credential_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_principal_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('provision', 'rotate', 'revoke')),
    acted_at TEXT NOT NULL
);

CREATE INDEX service_principal_credential_audit_lookup
    ON service_principal_credential_audit(tenant_id, service_principal_id, audit_id);
