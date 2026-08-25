def list_city_job_counts(connection, limit: int) -> list[dict[str, object]]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT city, job_count
        FROM mart.city_job_counts
        ORDER BY job_count DESC, city ASC
        LIMIT %s
        """,
        (limit,),
    )

    return [{"city": city, "job_count": job_count} for city, job_count in cursor.fetchall()]


def list_city_salary_stats(connection, limit: int) -> list[dict[str, object]]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT city, job_count, avg_salary_min, avg_salary_max, avg_salary_mid
        FROM mart.city_salary_stats
        ORDER BY job_count DESC, city ASC
        LIMIT %s
        """,
        (limit,),
    )

    return [
        {
            "city": city,
            "job_count": job_count,
            "avg_salary_min": avg_salary_min,
            "avg_salary_max": avg_salary_max,
            "avg_salary_mid": avg_salary_mid,
        }
        for city, job_count, avg_salary_min, avg_salary_max, avg_salary_mid in cursor.fetchall()
    ]


def list_skill_job_counts(connection, limit: int) -> list[dict[str, object]]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT skill, job_count
        FROM mart.skill_job_counts
        ORDER BY job_count DESC, skill ASC
        LIMIT %s
        """,
        (limit,),
    )

    return [{"skill": skill, "job_count": job_count} for skill, job_count in cursor.fetchall()]
