CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.batches (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    row_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    CONSTRAINT batches_status_check CHECK (
        status IN (
            'running',
            'succeeded',
            'failed'
        )
    ),
    CONSTRAINT batches_row_count_check CHECK (row_count >= 0)
);