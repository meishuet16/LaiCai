-- Allow the artifact-writer capability to perform the repository's stored
-- service-principal/source/customer checks without granting event-table reads.
-- Context values are transaction-local assertions supplied by the trusted
-- backend after bearer authentication; they are not unforgeable DB identity.
CREATE POLICY artifact_authorized_principal_lookup ON service_principals
FOR SELECT TO retaniq_artifact_writer
USING (
    tenant_id = NULLIF(current_setting('retaniq.tenant_id', true), '')
    AND service_principal_id = NULLIF(current_setting('retaniq.service_principal_id', true), '')
);

CREATE POLICY artifact_authorized_source_lookup ON integrations
FOR SELECT TO retaniq_artifact_writer
USING (
    tenant_id = NULLIF(current_setting('retaniq.tenant_id', true), '')
    AND source = ANY(string_to_array(NULLIF(current_setting('retaniq.authorized_sources', true), ''), ','))
);

CREATE POLICY artifact_authorized_category_lookup ON integration_event_categories
FOR SELECT TO retaniq_artifact_writer
USING (
    tenant_id = NULLIF(current_setting('retaniq.tenant_id', true), '')
    AND source = ANY(string_to_array(NULLIF(current_setting('retaniq.authorized_sources', true), ''), ','))
);

CREATE POLICY artifact_authorized_identity_lookup ON customer_identities
FOR SELECT TO retaniq_artifact_writer
USING (
    tenant_id = NULLIF(current_setting('retaniq.tenant_id', true), '')
    AND source = ANY(string_to_array(NULLIF(current_setting('retaniq.authorized_sources', true), ''), ','))
);

GRANT SELECT ON TABLE
    service_principals, integrations, integration_event_categories, customer_identities
TO retaniq_artifact_writer;
