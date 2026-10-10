-- 07B-1: least-privilege RLS foundation. Capability roles must be bootstrapped
-- by a reviewed administrator procedure before this transactional migration.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON TABLE
    tenants, integrations, customers, customer_identities, canonical_events,
    usage_events, billing_events, subscriptions, subscription_events,
    feature_snapshots, churn_labels, predictions, service_principals,
    subscription_owners, integration_event_categories, dataset_identity,
    observation_coverage, synthetic_import_checkpoints, retaniq_schema_migrations
FROM PUBLIC;

DO $revoke_exposed$
DECLARE
    exposed_role TEXT;
BEGIN
    FOREACH exposed_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = exposed_role) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE tenants, integrations, customers, customer_identities, canonical_events, usage_events, billing_events, subscriptions, subscription_events, feature_snapshots, churn_labels, predictions, service_principals, subscription_owners, integration_event_categories, dataset_identity, observation_coverage, synthetic_import_checkpoints, retaniq_schema_migrations FROM %I',
                exposed_role
            );
            EXECUTE format('REVOKE CREATE ON SCHEMA public FROM %I', exposed_role);
        END IF;
    END LOOP;
END
$revoke_exposed$;

GRANT USAGE ON SCHEMA public TO
    retaniq_backend, retaniq_inference_reader, retaniq_artifact_writer,
    retaniq_decision_service, retaniq_dashboard_reader, retaniq_maintenance,
    retaniq_authenticator;
REVOKE CREATE ON SCHEMA public FROM
    retaniq_backend, retaniq_inference_reader, retaniq_artifact_writer,
    retaniq_decision_service, retaniq_dashboard_reader, retaniq_maintenance,
    retaniq_authenticator;

-- Clear any grants established by local defaults or a hosted platform's
-- default ACLs. Explicit capability grants below are the complete allowlist.
REVOKE ALL ON TABLE
    tenants, integrations, customers, customer_identities, canonical_events,
    usage_events, billing_events, subscriptions, subscription_events,
    feature_snapshots, churn_labels, predictions, service_principals,
    subscription_owners, integration_event_categories, dataset_identity,
    observation_coverage, synthetic_import_checkpoints, retaniq_schema_migrations
FROM retaniq_backend, retaniq_inference_reader, retaniq_artifact_writer,
     retaniq_decision_service, retaniq_dashboard_reader, retaniq_maintenance;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC,
     retaniq_backend, retaniq_inference_reader, retaniq_artifact_writer,
     retaniq_decision_service, retaniq_dashboard_reader, retaniq_maintenance;

-- Narrow authentication bootstrap: token digests are supplied by trusted
-- Python after hashing a bearer token. These fixed-search_path functions
-- reveal only the matching principal and install its tenant GUC transaction-
-- locally. Raw credential tables remain RLS-protected. The DB login itself is
-- still trusted-backend-only; arbitrary SQL with that credential can spoof a
-- custom GUC, which is explicitly tested and documented.
CREATE FUNCTION retaniq_authenticate_integration(p_token_digest TEXT)
RETURNS TABLE (
    integration_id TEXT, tenant_id TEXT, source TEXT,
    authorized_purposes_json TEXT, schema_version TEXT, mapping_version TEXT,
    category TEXT
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    verified_tenant TEXT;
BEGIN
    SELECT i.tenant_id INTO verified_tenant
    FROM public.integrations AS i
    WHERE i.token_digest = p_token_digest;
    IF verified_tenant IS NULL THEN
        RETURN;
    END IF;
    PERFORM pg_catalog.set_config('retaniq.tenant_id', verified_tenant, true);
    RETURN QUERY
    SELECT i.integration_id, i.tenant_id, i.source,
           i.authorized_purposes_json, i.schema_version, i.mapping_version,
           c.category
    FROM public.integrations AS i
    LEFT JOIN public.integration_event_categories AS c
      ON c.tenant_id = i.tenant_id AND c.source = i.source
    WHERE i.token_digest = p_token_digest
    ORDER BY c.category;
END
$function$;

CREATE FUNCTION retaniq_authenticate_service_principal(p_token_digest TEXT)
RETURNS TABLE (
    service_principal_id TEXT, tenant_id TEXT, role TEXT,
    authorized_sources_json TEXT, authorized_purposes_json TEXT
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $function$
DECLARE
    verified_tenant TEXT;
BEGIN
    SELECT s.tenant_id INTO verified_tenant
    FROM public.service_principals AS s
    WHERE s.token_digest = p_token_digest;
    IF verified_tenant IS NULL THEN
        RETURN;
    END IF;
    PERFORM pg_catalog.set_config('retaniq.tenant_id', verified_tenant, true);
    RETURN QUERY
    SELECT s.service_principal_id, s.tenant_id, s.role,
           s.authorized_sources_json, s.authorized_purposes_json
    FROM public.service_principals AS s
    WHERE s.token_digest = p_token_digest;
END
$function$;

REVOKE ALL ON FUNCTION retaniq_authenticate_integration(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION retaniq_authenticate_service_principal(TEXT) FROM PUBLIC;
ALTER FUNCTION retaniq_authenticate_integration(TEXT) OWNER TO retaniq_authenticator;
ALTER FUNCTION retaniq_authenticate_service_principal(TEXT) OWNER TO retaniq_authenticator;
GRANT EXECUTE ON FUNCTION retaniq_authenticate_integration(TEXT),
    retaniq_authenticate_service_principal(TEXT) TO retaniq_backend;

-- The custom GUC is a trusted-backend assertion, not a credential. It is
-- transaction-local and fails closed when missing/empty/invalid. A client
-- holding this shared DB login can spoof it; see the acceptance document.
DO $policy$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'tenants', 'integrations', 'customers', 'customer_identities',
        'canonical_events', 'usage_events', 'billing_events', 'subscriptions',
        'subscription_events', 'feature_snapshots', 'churn_labels', 'predictions',
        'service_principals', 'subscription_owners', 'integration_event_categories',
        'observation_coverage'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('CREATE POLICY tenant_backend_scope ON %I FOR ALL TO retaniq_backend, retaniq_maintenance USING (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true)) WITH CHECK (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true))', table_name);
    END LOOP;

    FOREACH table_name IN ARRAY ARRAY[
        'customers', 'customer_identities', 'canonical_events', 'usage_events',
        'billing_events', 'subscriptions', 'subscription_events',
        'integration_event_categories', 'observation_coverage'
    ] LOOP
        EXECUTE format('CREATE POLICY tenant_inference_select ON %I FOR SELECT TO retaniq_inference_reader USING (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true))', table_name);
    END LOOP;

    FOREACH table_name IN ARRAY ARRAY['feature_snapshots', 'churn_labels', 'predictions'] LOOP
        EXECUTE format('CREATE POLICY tenant_artifact_scope ON %I FOR ALL TO retaniq_artifact_writer USING (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true)) WITH CHECK (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true))', table_name);
        EXECUTE format('CREATE POLICY tenant_decision_select ON %I FOR SELECT TO retaniq_decision_service USING (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true))', table_name);
    END LOOP;
    EXECUTE 'CREATE POLICY tenant_dashboard_customers ON customers FOR SELECT TO retaniq_dashboard_reader USING (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true))';
    EXECUTE 'CREATE POLICY tenant_dashboard_predictions ON predictions FOR SELECT TO retaniq_dashboard_reader USING (NULLIF(current_setting(''retaniq.tenant_id'', true), '''') IS NOT NULL AND tenant_id = current_setting(''retaniq.tenant_id'', true))';

    FOREACH table_name IN ARRAY ARRAY['integrations', 'integration_event_categories', 'service_principals'] LOOP
        EXECUTE format('CREATE POLICY restricted_authenticator_lookup ON %I FOR SELECT TO retaniq_authenticator USING (current_user = ''retaniq_authenticator'')', table_name);
    END LOOP;

    FOREACH table_name IN ARRAY ARRAY['dataset_identity', 'synthetic_import_checkpoints'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('CREATE POLICY global_maintenance_only ON %I FOR ALL TO retaniq_maintenance USING (pg_catalog.pg_has_role(current_user, ''retaniq_maintenance'', ''MEMBER'')) WITH CHECK (pg_catalog.pg_has_role(current_user, ''retaniq_maintenance'', ''MEMBER''))', table_name);
    END LOOP;
END
$policy$;

GRANT SELECT, INSERT, UPDATE ON TABLE
    tenants, integrations, customers, customer_identities, canonical_events,
    usage_events, billing_events, subscriptions, subscription_events,
    feature_snapshots, churn_labels, predictions, service_principals,
    subscription_owners, integration_event_categories, observation_coverage
TO retaniq_backend;
GRANT USAGE, SELECT ON SEQUENCE canonical_events_event_id_seq TO retaniq_backend;

GRANT SELECT ON TABLE
    customers, customer_identities, canonical_events, usage_events,
    billing_events, subscriptions, subscription_events,
    integration_event_categories, observation_coverage
TO retaniq_inference_reader;
GRANT SELECT, INSERT ON TABLE feature_snapshots, churn_labels, predictions
TO retaniq_artifact_writer;
GRANT SELECT ON TABLE predictions TO retaniq_decision_service;
GRANT SELECT ON TABLE customers, predictions TO retaniq_dashboard_reader;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    tenants, integrations, customers, customer_identities, canonical_events,
    usage_events, billing_events, subscriptions, subscription_events,
    feature_snapshots, churn_labels, predictions, service_principals,
    subscription_owners, integration_event_categories, observation_coverage
TO retaniq_maintenance;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE dataset_identity, synthetic_import_checkpoints
TO retaniq_maintenance;
GRANT USAGE, SELECT ON SEQUENCE canonical_events_event_id_seq TO retaniq_maintenance;
GRANT SELECT ON TABLE integrations, integration_event_categories, service_principals
TO retaniq_authenticator;

-- Keep global import state and migration metadata outside all runtime grants.
REVOKE ALL ON TABLE dataset_identity, synthetic_import_checkpoints,
    retaniq_schema_migrations FROM retaniq_backend, retaniq_inference_reader,
    retaniq_artifact_writer, retaniq_decision_service,
    retaniq_dashboard_reader, retaniq_maintenance;
