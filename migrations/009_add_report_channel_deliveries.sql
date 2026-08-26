CREATE TABLE IF NOT EXISTS ops.report_channel_deliveries (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    report_key TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    external_message_id TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error_type TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT report_channel_deliveries_status_check
        CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'uncertain')),
    CONSTRAINT report_channel_deliveries_attempts_check CHECK (attempts >= 0),
    CONSTRAINT report_channel_deliveries_unique UNIQUE (report_date, report_key, channel)
);

COMMENT ON TABLE ops.report_channel_deliveries IS
    'Independent idempotency state for each report delivery channel.';
