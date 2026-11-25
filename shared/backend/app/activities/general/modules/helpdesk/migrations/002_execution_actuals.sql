-- Additive private, non-posting execution history. No native source alterations.
-- Idempotent for the service create_all boot order; the caller adopts only an
-- exact column match and still verifies RLS, grants and append-only triggers.
CREATE TABLE IF NOT EXISTS helpdesk_execution_revisions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
 source_module varchar(32) NOT NULL CHECK (source_module IN ('field_service','real_estate')),
 source_id varchar(36) NOT NULL,
 revision integer NOT NULL CHECK (revision > 0),
 user_id uuid NOT NULL,
 fingerprint varchar(64) NOT NULL,
 payload jsonb NOT NULL,
 resource_labels jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT uq_helpdesk_execution_source_revision UNIQUE (tenant_id,source_module,source_id,revision)
);
CREATE INDEX IF NOT EXISTS ix_helpdesk_execution_revisions_tenant_id ON helpdesk_execution_revisions(tenant_id);
ALTER TABLE helpdesk_execution_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE helpdesk_execution_revisions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON helpdesk_execution_revisions;
CREATE POLICY tenant_isolation ON helpdesk_execution_revisions
 USING (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
 WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid);
-- Normal application gets append/read only, not UPDATE or DELETE on history.
GRANT SELECT,INSERT ON helpdesk_execution_revisions TO mizan_app;
REVOKE UPDATE,DELETE,TRUNCATE ON helpdesk_execution_revisions FROM mizan_app;
-- Existing shared grant helper may later widen table grants. This table-local
-- guard preserves append-only behavior under that helper without changing it.
CREATE OR REPLACE FUNCTION helpdesk_actuals_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF current_user = 'mizan_app' THEN
  RAISE EXCEPTION 'Execution history is append-only for application role';
 END IF;
 RETURN OLD;
END;
$$;
DROP TRIGGER IF EXISTS helpdesk_actuals_no_rewrite ON helpdesk_execution_revisions;
CREATE TRIGGER helpdesk_actuals_no_rewrite BEFORE UPDATE OR DELETE ON helpdesk_execution_revisions
 FOR EACH ROW EXECUTE FUNCTION helpdesk_actuals_append_only();
DROP TRIGGER IF EXISTS helpdesk_actuals_no_truncate ON helpdesk_execution_revisions;
CREATE TRIGGER helpdesk_actuals_no_truncate BEFORE TRUNCATE ON helpdesk_execution_revisions
 FOR EACH STATEMENT EXECUTE FUNCTION helpdesk_actuals_append_only();
