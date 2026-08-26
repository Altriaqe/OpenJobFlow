"""ops 批次状态写入：记录 ETL 运行生命周期和错误。"""

def start_batch(connection, source: str) -> int:
    """在数据库中插入一个新的运行中的批次，并返回其 ID"""
    cursor = connection.cursor()

    sql = """
    INSERT INTO ops.batches (source, status)
    VALUES (%s, 'running')
    RETURNING id
    """

    cursor.execute(sql, (source,))

    result = cursor.fetchone()

    return result[0]


def finish_batch(connection, batch_id: int, row_count: int) -> None:
    """将批次标记为成功，并记录完成时间和处理数量。"""
    cursor = connection.cursor()

    sql = """
        UPDATE ops.batches
        SET
            status = 'succeeded',
            finished_at = CURRENT_TIMESTAMP,
            row_count = %s
        WHERE id = %s
    """

    cursor.execute(sql, (row_count, batch_id))


def fail_batch(
    connection,
    batch_id: int,
    error_message: str,
) -> None:
    """将批次标记为失败，并记录结束时间和错误信息。"""
    cursor = connection.cursor()

    sql = """
        UPDATE ops.batches
        SET
            status = 'failed',
            finished_at = CURRENT_TIMESTAMP,
            error_message = %s
        WHERE id = %s
    """

    cursor.execute(sql, (error_message, batch_id))
