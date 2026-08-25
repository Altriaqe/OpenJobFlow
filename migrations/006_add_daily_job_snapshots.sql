CREATE TABLE IF NOT EXISTS core.job_snapshots (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    search_keyword TEXT NOT NULL,
    batch_id BIGINT NOT NULL UNIQUE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    city_count SMALLINT NOT NULL,
    cities TEXT[] NOT NULL,
    pages_per_city SMALLINT NOT NULL,
    details_included BOOLEAN NOT NULL,
    status TEXT NOT NULL DEFAULT 'succeeded',
    CONSTRAINT job_snapshots_batch_id_fkey
        FOREIGN KEY (batch_id)
        REFERENCES ops.batches (id),
    CONSTRAINT job_snapshots_date_keyword_key
        UNIQUE (snapshot_date, search_keyword),
    CONSTRAINT job_snapshots_city_count_check
        CHECK (city_count > 0),
    CONSTRAINT job_snapshots_cities_check
        CHECK (city_count = cardinality(cities)),
    CONSTRAINT job_snapshots_pages_check
        CHECK (pages_per_city > 0),
    CONSTRAINT job_snapshots_status_check
        CHECK (status = 'succeeded')
);

CREATE TABLE IF NOT EXISTS core.job_snapshot_items (
    snapshot_id BIGINT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    city TEXT NOT NULL,
    salary_text TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_unit TEXT,
    salary_months SMALLINT,
    skills TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT job_snapshot_items_snapshot_id_fkey
        FOREIGN KEY (snapshot_id)
        REFERENCES core.job_snapshots (id)
        ON DELETE CASCADE,
    CONSTRAINT job_snapshot_items_pkey
        PRIMARY KEY (snapshot_id, source, external_id),
    CONSTRAINT job_snapshot_items_salary_values_check CHECK (
        (salary_text IS NULL
         AND salary_min IS NULL
         AND salary_max IS NULL
         AND salary_unit IS NULL
         AND salary_months IS NULL)
        OR
        (salary_text IS NOT NULL
         AND salary_min > 0
         AND salary_max >= salary_min
         AND salary_unit IN ('K_PER_MONTH', 'CNY_PER_DAY', 'CNY_PER_HOUR')
         AND (salary_months IS NULL OR salary_months > 0)
         AND (salary_unit = 'K_PER_MONTH' OR salary_months IS NULL))
    )
);

CREATE INDEX IF NOT EXISTS job_snapshots_keyword_date_idx
    ON core.job_snapshots (search_keyword, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS job_snapshot_items_snapshot_city_idx
    ON core.job_snapshot_items (snapshot_id, city);

CREATE TABLE IF NOT EXISTS ops.report_deliveries (
    snapshot_id BIGINT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    text_message_id BIGINT,
    photo_message_id BIGINT,
    text_attempts SMALLINT NOT NULL DEFAULT 0,
    photo_attempts SMALLINT NOT NULL DEFAULT 0,
    last_error_type TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT report_deliveries_snapshot_id_fkey
        FOREIGN KEY (snapshot_id)
        REFERENCES core.job_snapshots (id)
        ON DELETE CASCADE,
    CONSTRAINT report_deliveries_status_check CHECK (
        status IN (
            'pending',
            'text_sent',
            'completed',
            'partial_failed',
            'failed'
        )
    ),
    CONSTRAINT report_deliveries_attempts_check CHECK (
        text_attempts >= 0
        AND photo_attempts >= 0
    ),
    CONSTRAINT report_deliveries_message_ids_check CHECK (
        (text_message_id IS NULL OR text_message_id > 0)
        AND (photo_message_id IS NULL OR photo_message_id > 0)
    ),
    CONSTRAINT report_deliveries_state_check CHECK (
        (status IN ('pending', 'failed')
         AND text_message_id IS NULL
         AND photo_message_id IS NULL)
        OR
        (status IN ('text_sent', 'partial_failed')
         AND text_message_id IS NOT NULL
         AND photo_message_id IS NULL)
        OR
        (status = 'completed'
         AND text_message_id IS NOT NULL
         AND photo_message_id IS NOT NULL)
    )
);
