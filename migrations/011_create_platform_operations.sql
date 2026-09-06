CREATE TABLE IF NOT EXISTS ops.platform_operation_runs (
    id BIGSERIAL PRIMARY KEY,
    kind TEXT NOT NULL,
    report_date DATE,
    status TEXT NOT NULL DEFAULT 'running',
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    CONSTRAINT platform_operation_kind_check CHECK (kind IN ('server_check', 'recovery_run')),
    CONSTRAINT platform_operation_status_check CHECK (status IN ('running', 'succeeded', 'failed'))
);

CREATE TABLE IF NOT EXISTS ops.platform_check_results (
    id BIGSERIAL PRIMARY KEY,
    operation_id BIGINT NOT NULL REFERENCES ops.platform_operation_runs(id),
    check_name TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    error_message TEXT,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT platform_check_status_check CHECK (status IN ('succeeded', 'failed'))
);

CREATE TABLE IF NOT EXISTS ops.platform_delivery_actions (
    id BIGSERIAL PRIMARY KEY,
    operation_id BIGINT REFERENCES ops.platform_operation_runs(id),
    report_date DATE NOT NULL,
    channel TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    external_id TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT platform_delivery_channel_check CHECK (channel IN ('telegram', 'wechat')),
    CONSTRAINT platform_delivery_action_check CHECK (action IN ('manual_delivery', 'recovery_delivery')),
    CONSTRAINT platform_delivery_status_check CHECK (status IN ('running', 'sent', 'created', 'failed', 'uncertain')),
    CONSTRAINT platform_delivery_idempotency UNIQUE (report_date, channel, action)
);
