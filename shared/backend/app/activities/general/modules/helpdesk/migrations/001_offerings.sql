-- Additive draft only. Wire into the tracked atomic migration runner after review.
-- No existing source tables or grants are changed. Do not mark applied on error.
CREATE TABLE helpdesk_offerings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
        DEFAULT NULLIF(current_setting('app.tenant_id', true), '')::uuid,
    name varchar(256) NOT NULL,
    description text NOT NULL DEFAULT '',
    starting_amount numeric(14,2) NOT NULL CONSTRAINT helpdesk_amount_nonnegative CHECK (starting_amount >= 0),
    currency varchar(3) NOT NULL CHECK (currency IN ('EGP','USD','EUR','GBP','SAR','AED','QAR')),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_helpdesk_offerings_tenant_id ON helpdesk_offerings(tenant_id);
ALTER TABLE helpdesk_offerings ENABLE ROW LEVEL SECURITY;
ALTER TABLE helpdesk_offerings FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON helpdesk_offerings
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
           OR current_setting('app.bypass', true) = 'on')
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
           OR current_setting('app.bypass', true) = 'on');
-- Run application-role grant through the established migration grant step.
