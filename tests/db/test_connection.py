import pytest

from jobflow.db.connection import DatabaseConfigError
from jobflow.db.connection import connect_postgres


@pytest.mark.parametrize(
    "missing_variable",
    [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ],
)
def test_connect_postgres_config_error_when_required_variable_missing(
    monkeypatch: pytest.MonkeyPatch, missing_variable: str
) -> None:
    monkeypatch.setenv("POSTGRES_DB", "jobflow")
    monkeypatch.setenv("POSTGRES_USER", "jobflow")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-password")
    monkeypatch.delenv(missing_variable, raising=False)

    def fail_connect(**_: object) -> None:
        pytest.fail("配置缺失时不应调用 psycopg.connect")

    monkeypatch.setattr("psycopg.connect", fail_connect)
    with pytest.raises(DatabaseConfigError) as exc_info:
        connect_postgres()

    assert missing_variable in str(exc_info.value)


def test_connect_postgres_passes_config_to_psycopg(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_DB", "jobflow")
    monkeypatch.setenv("POSTGRES_USER", "jobflow")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test-password")

    connect_args = {}
    fake_connection = object()

    def fake_connect(*, host, port, dbname, user, password):
        connect_args.update(
            {
                "host": host,
                "port": port,
                "dbname": dbname,
                "user": user,
                "password": password,
            }
        )

        return fake_connection

    monkeypatch.setattr("psycopg.connect", fake_connect)
    result = connect_postgres()
    assert result is fake_connection
    assert connect_args == {
        "host": "127.0.0.1",
        "port": "5432",
        "dbname": "jobflow",
        "user": "jobflow",
        "password": "test-password",
    }
