-- Reviewed, cluster-level bootstrap for the 07B-1 NOLOGIN capability roles.
-- Run as a trusted database administrator before migration 005. This file
-- creates no login, password, superuser, or BYPASSRLS credentials.
DO $bootstrap$
DECLARE
    role_name TEXT;
    role_attributes RECORD;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'retaniq_backend',
        'retaniq_inference_reader',
        'retaniq_artifact_writer',
        'retaniq_decision_service',
        'retaniq_dashboard_reader',
        'retaniq_maintenance',
        'retaniq_authenticator'
    ] LOOP
        SELECT rolcanlogin, rolsuper, rolbypassrls, rolinherit
        INTO role_attributes
        FROM pg_catalog.pg_roles WHERE rolname = role_name;
        IF NOT FOUND THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOBYPASSRLS', role_name);
        ELSIF role_attributes.rolcanlogin OR role_attributes.rolsuper
              OR role_attributes.rolbypassrls OR role_attributes.rolinherit THEN
            RAISE EXCEPTION 'existing RetainIQ capability role requires manual review';
        END IF;
    END LOOP;
END
$bootstrap$;
