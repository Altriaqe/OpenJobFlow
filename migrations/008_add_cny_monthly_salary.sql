ALTER TABLE core.jobs
DROP CONSTRAINT IF EXISTS jobs_salary_values_check;

ALTER TABLE core.jobs
ADD CONSTRAINT jobs_salary_values_check CHECK (
    (salary_text IS NULL
     AND salary_min IS NULL
     AND salary_max IS NULL
     AND salary_unit IS NULL
     AND salary_months IS NULL)
    OR
    (salary_text IS NOT NULL
     AND salary_min IS NULL
     AND salary_max IS NULL
     AND salary_unit IS NULL
     AND salary_months IS NULL)
    OR
    (salary_text IS NOT NULL
     AND salary_min > 0
     AND salary_max >= salary_min
     AND salary_unit IN (
         'K_PER_MONTH',
         'CNY_PER_MONTH',
         'CNY_PER_DAY',
         'CNY_PER_HOUR'
     )
     AND (salary_months IS NULL OR salary_months > 0)
     AND (salary_unit = 'K_PER_MONTH' OR salary_months IS NULL))
);

ALTER TABLE core.job_snapshot_items
DROP CONSTRAINT IF EXISTS job_snapshot_items_salary_values_check;

ALTER TABLE core.job_snapshot_items
ADD CONSTRAINT job_snapshot_items_salary_values_check CHECK (
    (salary_text IS NULL
     AND salary_min IS NULL
     AND salary_max IS NULL
     AND salary_unit IS NULL
     AND salary_months IS NULL)
    OR
    (salary_text IS NOT NULL
     AND salary_min IS NULL
     AND salary_max IS NULL
     AND salary_unit IS NULL
     AND salary_months IS NULL)
    OR
    (salary_text IS NOT NULL
     AND salary_min > 0
     AND salary_max >= salary_min
     AND salary_unit IN (
         'K_PER_MONTH',
         'CNY_PER_MONTH',
         'CNY_PER_DAY',
         'CNY_PER_HOUR'
     )
     AND (salary_months IS NULL OR salary_months > 0)
     AND (salary_unit = 'K_PER_MONTH' OR salary_months IS NULL))
);

CREATE OR REPLACE VIEW mart.city_salary_stats AS
SELECT
    city,
    COUNT(*) AS job_count,
    ROUND(AVG(salary_min_k), 2) AS avg_salary_min,
    ROUND(AVG(salary_max_k), 2) AS avg_salary_max,
    ROUND(AVG((salary_min_k + salary_max_k) / 2.0), 2) AS avg_salary_mid
FROM (
    SELECT
        city,
        CASE
            WHEN salary_unit = 'CNY_PER_MONTH' THEN salary_min / 1000.0
            ELSE salary_min
        END AS salary_min_k,
        CASE
            WHEN salary_unit = 'CNY_PER_MONTH' THEN salary_max / 1000.0
            ELSE salary_max
        END AS salary_max_k
    FROM core.jobs
    WHERE salary_unit IN ('K_PER_MONTH', 'CNY_PER_MONTH')
      AND salary_min IS NOT NULL
      AND salary_max IS NOT NULL
) AS normalized_monthly_salaries
GROUP BY city;
