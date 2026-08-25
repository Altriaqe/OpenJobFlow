CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.job_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id BIGINT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT job_records_batch_id_fkey
        FOREIGN KEY (batch_id)
        REFERENCES ops.batches (id),
    CONSTRAINT job_records_batch_source_external_id_key
        UNIQUE (batch_id, source, external_id)
);
