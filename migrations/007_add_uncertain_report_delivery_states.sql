ALTER TABLE ops.report_deliveries
    DROP CONSTRAINT IF EXISTS report_deliveries_status_check,
    DROP CONSTRAINT IF EXISTS report_deliveries_state_check;

ALTER TABLE ops.report_deliveries
    ADD CONSTRAINT report_deliveries_status_check CHECK (
        status IN (
            'pending',
            'text_sending',
            'text_sent',
            'text_failed',
            'text_uncertain',
            'photo_sending',
            'photo_failed',
            'photo_uncertain',
            'completed',
            'completed_text_uncertain',
            'failed',
            'partial_failed'
        )
    ),
    ADD CONSTRAINT report_deliveries_state_check CHECK (
        (status IN ('pending', 'text_sending', 'text_failed', 'text_uncertain', 'failed')
         AND text_message_id IS NULL
         AND photo_message_id IS NULL)
        OR
        (status IN ('text_sent', 'partial_failed')
         AND text_message_id IS NOT NULL
         AND photo_message_id IS NULL)
        OR
        (status IN ('photo_sending', 'photo_failed', 'photo_uncertain')
         AND photo_message_id IS NULL)
        OR
        (status = 'completed'
         AND text_message_id IS NOT NULL
         AND photo_message_id IS NOT NULL)
        OR
        (status = 'completed_text_uncertain'
         AND text_message_id IS NULL
         AND photo_message_id IS NOT NULL)
    );
