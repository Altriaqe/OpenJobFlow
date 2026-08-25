from jobflow.models.job import JobRecord


def insert_job(connection, job: JobRecord) -> None:
    """将岗位数据插入数据库，如果已存在则更新"""
    cursor = connection.cursor()
    sql = """
        INSERT INTO core.jobs (
            source,
            external_id,
            title,
            company,
            city,
            detail_url,
            salary_text,
            salary_min,
            salary_max,
            salary_unit,
            salary_months,
            skills
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source, external_id) DO UPDATE SET 
            title = EXCLUDED.title,
            company = EXCLUDED.company,
            city = EXCLUDED.city,
            detail_url = EXCLUDED.detail_url,
            salary_text = EXCLUDED.salary_text,
            salary_min = EXCLUDED.salary_min,
            salary_max = EXCLUDED.salary_max,
            salary_unit = EXCLUDED.salary_unit,
            salary_months = EXCLUDED.salary_months,
            skills = EXCLUDED.skills,
            last_seen_at = CURRENT_TIMESTAMP,
            updated_at = CASE
                WHEN core.jobs.title IS DISTINCT FROM EXCLUDED.title
                OR core.jobs.company IS DISTINCT FROM EXCLUDED.company
                OR core.jobs.city IS DISTINCT FROM EXCLUDED.city
                OR core.jobs.detail_url IS DISTINCT FROM EXCLUDED.detail_url
                OR core.jobs.salary_text IS DISTINCT FROM EXCLUDED.salary_text
                OR core.jobs.salary_min IS DISTINCT FROM EXCLUDED.salary_min
                OR core.jobs.salary_max IS DISTINCT FROM EXCLUDED.salary_max
                OR core.jobs.salary_unit IS DISTINCT FROM EXCLUDED.salary_unit
                OR core.jobs.salary_months IS DISTINCT FROM EXCLUDED.salary_months
                OR core.jobs.skills IS DISTINCT FROM EXCLUDED.skills
                THEN CURRENT_TIMESTAMP
                ELSE core.jobs.updated_at
            END
    """
    params = (
        job.source,
        job.external_id,
        job.title,
        job.company,
        job.city,
        job.detail_url,
        job.salary_text,
        job.salary_min,
        job.salary_max,
        job.salary_unit,
        job.salary_months,
        job.skills,
    )

    cursor.execute(sql, params)  # 执行 SQL 语句


def insert_jobs(connection, jobs: list[JobRecord]) -> None:
    """批量插入岗位数据，如果已存在则更新"""
    for job in jobs:
        insert_job(connection, job)
