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
         'CNY_PER_WEEK',
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
         'CNY_PER_WEEK',
         'CNY_PER_HOUR'
     )
     AND (salary_months IS NULL OR salary_months > 0)
     AND (salary_unit = 'K_PER_MONTH' OR salary_months IS NULL))
);
