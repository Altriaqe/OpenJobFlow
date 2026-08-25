from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from jobflow.api.analytics import get_connection
from jobflow.api.app import create_app


def client_with_rows(rows):
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = rows
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    return TestClient(app), app, connection


def test_city_analytics_returns_rows_and_default_limit():
    client, app, connection = client_with_rows([("Lanzhou", 12)])
    try:
        response = client.get("/analytics/cities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [{"city": "Lanzhou", "job_count": 12}]
    _, params = connection.cursor.return_value.execute.call_args.args
    assert params == (20,)


def test_city_analytics_rejects_limit_outside_range():
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: Mock()
    client = TestClient(app)

    try:
        assert client.get("/analytics/cities?limit=0").status_code == 422
        assert client.get("/analytics/cities?limit=101").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_city_analytics_returns_empty_array_when_view_has_no_rows():
    client, app, _ = client_with_rows([])
    try:
        response = client.get("/analytics/cities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


def test_city_analytics_hides_database_error_details():
    connection = Mock()
    connection.cursor.return_value.execute.side_effect = RuntimeError("internal database detail")
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    client = TestClient(app)
    try:
        response = client.get("/analytics/cities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "analytics database unavailable"}


def test_city_salary_analytics_returns_rows_and_default_limit():
    rows = [("上海", 3, 15.0, 25.0, 20.0)]
    client, app, connection = client_with_rows(rows)
    try:
        response = client.get("/analytics/salaries/cities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "city": "上海",
            "job_count": 3,
            "avg_salary_min": 15.0,
            "avg_salary_max": 25.0,
            "avg_salary_mid": 20.0,
        }
    ]
    _, params = connection.cursor.return_value.execute.call_args.args
    assert params == (20,)


def test_skill_analytics_returns_rows_and_requested_limit():
    client, app, connection = client_with_rows([("Python", 8)])
    try:
        response = client.get("/analytics/skills?limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [{"skill": "Python", "job_count": 8}]
    _, params = connection.cursor.return_value.execute.call_args.args
    assert params == (10,)


@pytest.mark.parametrize(
    "path",
    ["/analytics/salaries/cities", "/analytics/skills"],
)
def test_new_analytics_reject_limit_outside_range(path):
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: Mock()
    client = TestClient(app)
    try:
        assert client.get(f"{path}?limit=0").status_code == 422
        assert client.get(f"{path}?limit=101").status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "path",
    ["/analytics/salaries/cities", "/analytics/skills"],
)
def test_new_analytics_returns_empty_array(path):
    client, app, _ = client_with_rows([])
    try:
        response = client.get(path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "path",
    ["/analytics/salaries/cities", "/analytics/skills"],
)
def test_new_analytics_hides_database_error_details(path):
    connection = Mock()
    connection.cursor.return_value.execute.side_effect = RuntimeError("database secret")
    app = create_app()
    app.dependency_overrides[get_connection] = lambda: connection
    client = TestClient(app)
    try:
        response = client.get(path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "analytics database unavailable"}
