from pathlib import Path


def test_salary_skill_migration_defines_core_fields_constraints_and_views() -> None:
    sql = Path("migrations/005_add_salary_skill_analytics.sql").read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS salary_text TEXT" in sql
    assert "ADD COLUMN IF NOT EXISTS salary_min INTEGER" in sql
    assert "ADD COLUMN IF NOT EXISTS salary_max INTEGER" in sql
    assert "ADD COLUMN IF NOT EXISTS salary_unit TEXT" in sql
    assert "ADD COLUMN IF NOT EXISTS salary_months SMALLINT" in sql
    assert "ADD COLUMN IF NOT EXISTS skills TEXT[]" in sql
    assert "jobs_salary_values_check" in sql
    assert "salary_max >= salary_min" in sql
    assert "salary_unit IN ('K_PER_MONTH', 'CNY_PER_DAY', 'CNY_PER_HOUR')" in sql
    assert "CREATE OR REPLACE VIEW mart.city_salary_stats" in sql
    assert "WHERE salary_unit = 'K_PER_MONTH'" in sql
    assert "CREATE OR REPLACE VIEW mart.skill_job_counts" in sql
    assert "unnest(skills)" in sql


def test_cny_monthly_salary_migration_updates_both_tables_and_view() -> None:
    path = Path("migrations/008_add_cny_monthly_salary.sql")

    assert path.exists()
    normalized = " ".join(path.read_text(encoding="utf-8").split())

    assert "ALTER TABLE core.jobs DROP CONSTRAINT IF EXISTS jobs_salary_values_check" in normalized
    assert (
        "ALTER TABLE core.job_snapshot_items DROP CONSTRAINT IF EXISTS "
        "job_snapshot_items_salary_values_check"
    ) in normalized
    assert "ADD CONSTRAINT jobs_salary_values_check" in normalized
    assert "ADD CONSTRAINT job_snapshot_items_salary_values_check" in normalized
    assert normalized.count("'CNY_PER_MONTH'") >= 5
    assert "salary_unit = 'K_PER_MONTH' OR salary_months IS NULL" in normalized
    assert "salary_text IS NOT NULL AND salary_min IS NULL" in normalized
    assert "CREATE OR REPLACE VIEW mart.city_salary_stats" in normalized
    assert "WHEN salary_unit = 'CNY_PER_MONTH' THEN salary_min / 1000.0" in normalized
    assert "WHEN salary_unit = 'CNY_PER_MONTH' THEN salary_max / 1000.0" in normalized
