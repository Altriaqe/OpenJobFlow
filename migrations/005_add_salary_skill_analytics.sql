ALTER TABLE core.jobs
ADD COLUMN IF NOT EXISTS salary_text TEXT,
ADD COLUMN IF NOT EXISTS salary_min INTEGER,
ADD COLUMN IF NOT EXISTS salary_max INTEGER,
ADD COLUMN IF NOT EXISTS salary_unit TEXT,
ADD COLUMN IF NOT EXISTS salary_months SMALLINT,
ADD COLUMN IF NOT EXISTS skills TEXT[] DEFAULT ARRAY[]::TEXT[];

UPDATE core.jobs
SET skills = ARRAY[]::TEXT[]
WHERE skills IS NULL;

ALTER TABLE core.jobs
ALTER COLUMN skills SET DEFAULT ARRAY[]::TEXT[],
ALTER COLUMN skills SET NOT NULL;

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
     AND salary_min > 0
     AND salary_max >= salary_min
     AND salary_unit IN ('K_PER_MONTH', 'CNY_PER_DAY', 'CNY_PER_HOUR')
     AND (salary_months IS NULL OR salary_months > 0)
     AND (salary_unit = 'K_PER_MONTH' OR salary_months IS NULL))
);

CREATE OR REPLACE VIEW mart.city_salary_stats AS
SELECT
    city,
    COUNT(*) AS job_count,
    ROUND(AVG(salary_min), 2) AS avg_salary_min,
    ROUND(AVG(salary_max), 2) AS avg_salary_max,
    ROUND(AVG((salary_min + salary_max) / 2.0), 2) AS avg_salary_mid
FROM core.jobs
WHERE salary_unit = 'K_PER_MONTH'
  AND salary_min IS NOT NULL
  AND salary_max IS NOT NULL
GROUP BY city;

CREATE OR REPLACE VIEW mart.skill_job_counts AS
SELECT
    skill,
    COUNT(*) AS job_count
FROM core.jobs
CROSS JOIN LATERAL unnest(skills) AS skill
GROUP BY skill;
