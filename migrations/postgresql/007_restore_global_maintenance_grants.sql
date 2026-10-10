-- Migration 005's final deny-list also revoked its intended maintenance
-- grants. Restore only the explicit global operational-table capabilities;
-- row access remains gated by the global_maintenance_only RLS policies.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    dataset_identity, synthetic_import_checkpoints
TO retaniq_maintenance;
