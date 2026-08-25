from decimal import Decimal

from jobflow.db.analytics import list_city_salary_stats, list_skill_job_counts


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = None

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.fake_cursor = FakeCursor(rows)

    def cursor(self):
        return self.fake_cursor


def test_list_city_salary_stats_returns_mapped_rows() -> None:
    connection = FakeConnection([("上海", 3, Decimal("15.00"), Decimal("25.00"), Decimal("20.00"))])

    result = list_city_salary_stats(connection, 20)

    sql, params = connection.fake_cursor.executed
    assert "FROM mart.city_salary_stats" in sql
    assert "ORDER BY job_count DESC, city ASC" in sql
    assert params == (20,)
    assert result == [
        {
            "city": "上海",
            "job_count": 3,
            "avg_salary_min": Decimal("15.00"),
            "avg_salary_max": Decimal("25.00"),
            "avg_salary_mid": Decimal("20.00"),
        }
    ]


def test_list_skill_job_counts_returns_mapped_rows() -> None:
    connection = FakeConnection([("Python", 8)])

    result = list_skill_job_counts(connection, 10)

    sql, params = connection.fake_cursor.executed
    assert "FROM mart.skill_job_counts" in sql
    assert "ORDER BY job_count DESC, skill ASC" in sql
    assert params == (10,)
    assert result == [{"skill": "Python", "job_count": 8}]
