from jobflow.db.batches import start_batch, finish_batch, fail_batch


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def fetchone(self):
        return (101,)


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()

    def cursor(self):
        return self.fake_cursor


def test_start_batch_inserts_running_batch_and_returns_id():
    """测试 start_batch() 函数是否正确插入一个运行中的批次并返回其 ID"""
    connection = FakeConnection()

    batch_id = start_batch(connection, "boss_zhipin")

    assert batch_id == 101

    sql, params = connection.fake_cursor.executed[0]

    assert "INSERT INTO ops.batches" in sql
    assert "RETURNING id" in sql
    assert params == ("boss_zhipin",)
    assert "running" in sql


def test_finish_batch_marks_batch_as_succeeded():
    """测试 finish_batch() 函数是否正确将批次标记为成功"""
    connection = FakeConnection()

    # 调用 finish_batch() 函数, 不返回任何值, 但会在 FakeCursor 中记录执行的 SQL
    finish_batch(connection, batch_id=101, row_count=30)

    sql, params = connection.fake_cursor.executed[0]

    assert "status = 'succeeded'" in sql
    assert "finished_at = CURRENT_TIMESTAMP" in sql
    assert "row_count = %s" in sql
    assert params == (30, 101)


def test_fail_batch_marks_batch_as_failed():
    connection = FakeConnection()

    fail_batch(
        connection,
        batch_id=101,
        error_message="数据库连接失败",
    )

    sql, params = connection.fake_cursor.executed[0]

    assert "UPDATE ops.batches" in sql
    assert "status = 'failed'" in sql
    assert "finished_at = CURRENT_TIMESTAMP" in sql
    assert "error_message = %s" in sql
    assert params == ("数据库连接失败", 101)
