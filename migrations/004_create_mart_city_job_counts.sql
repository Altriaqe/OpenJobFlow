CREATE SCHEMA IF NOT EXISTS mart;

CREATE OR REPLACE VIEW mart.city_job_counts AS
SELECT city, COUNT(*) AS job_count
FROM core.jobs
GROUP BY
    city;