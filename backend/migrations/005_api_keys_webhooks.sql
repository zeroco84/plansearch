-- PlanSearch Phase 5: Public API — Database Migration
-- Run this against the production database before deploying the v1 API.
-- Tables: api_keys, api_usage, webhooks, webhook_deliveries

-- ═══ API Keys ═══
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(64) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    environment VARCHAR(10) DEFAULT 'live',
    tier VARCHAR(20) NOT NULL DEFAULT 'developer',
    is_active BOOLEAN DEFAULT TRUE,
    calls_this_month INTEGER DEFAULT 0,
    monthly_quota INTEGER DEFAULT 1000,
    rate_limit_per_minute INTEGER DEFAULT 10,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

-- ═══ API Usage Logs ═══
CREATE TABLE IF NOT EXISTS api_usage (
    id BIGSERIAL PRIMARY KEY,
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    endpoint VARCHAR(100),
    status_code INTEGER,
    response_time_ms INTEGER,
    called_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_key_month ON api_usage(api_key_id, called_at);

-- ═══ Webhooks ═══
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    events JSONB DEFAULT '[]'::jsonb,
    filters JSONB DEFAULT '{}'::jsonb,
    secret_encrypted TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_delivered_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_webhooks_key ON webhooks(api_key_id);

-- ═══ Webhook Deliveries ═══
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event VARCHAR(50) NOT NULL,
    reg_ref VARCHAR(100),
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    http_status INTEGER,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wh_deliveries_pending
    ON webhook_deliveries(status, created_at)
    WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_wh_deliveries_webhook
    ON webhook_deliveries(webhook_id, created_at DESC);

-- ═══ Monthly quota reset — run via pg_cron on 1st of each month ═══
-- SELECT cron.schedule('reset-api-quotas', '0 0 1 * *', 'UPDATE api_keys SET calls_this_month = 0');

-- Verify
SELECT 'api_keys' AS table_name, COUNT(*) FROM api_keys
UNION ALL
SELECT 'api_usage', COUNT(*) FROM api_usage
UNION ALL
SELECT 'webhooks', COUNT(*) FROM webhooks
UNION ALL
SELECT 'webhook_deliveries', COUNT(*) FROM webhook_deliveries;
