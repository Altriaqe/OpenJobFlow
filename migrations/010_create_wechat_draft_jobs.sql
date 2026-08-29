CREATE TABLE IF NOT EXISTS ops.wechat_draft_jobs (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'uploading',
    draft_media_id TEXT,
    cover_media_id TEXT,
    trend_media_id TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT wechat_draft_jobs_status_check
        CHECK (status IN ('uploading', 'created', 'failed'))
);

COMMENT ON TABLE ops.wechat_draft_jobs IS
    'Idempotent status for automatically created WeChat Official Account drafts.';
