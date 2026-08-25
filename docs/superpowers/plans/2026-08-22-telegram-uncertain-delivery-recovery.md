# Telegram 防重复与只补图恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Telegram 超时从“自动重试并可能重复发送”改成“单次投递、结果不确定即停机等待人工确认”，并提供只补当日热力图的受保护恢复接口。

**Architecture:** PostgreSQL 的四条 `ops.report_deliveries` 记录共同组成一次多关键词日报投递状态机。服务在外部请求前用 `SELECT ... FOR UPDATE` 锁定四行、写入 `*_sending` 并提交，释放锁后只调用一次 Telegram；超时或连接中断记录为 `*_uncertain`。普通发送接口不能越过不确定状态，只有携带原 Bearer Token 且显式确认文字可见的恢复接口可以跳过文字、只发送图片。

**Tech Stack:** Python 3.12、requests、FastAPI、psycopg 3、PostgreSQL、pytest、Bash、Docker Compose、systemd。

## Global Constraints

- 多关键词日报的文字和图片每个阶段只允许 1 次 Telegram HTTP 请求。
- 超时、连接中断、HTTP 5xx、成功响应无法解析均属于“结果不确定”，禁止内部重试。
- HTTP 4xx（包括 429）、Telegram `ok=false`、非法 PNG、消息过长和缺配置属于明确失败。
- 外部 Telegram 请求期间不得持有 PostgreSQL 行锁。
- 普通发送接口不得自动恢复 `*_sending`、`*_failed`、`*_uncertain`、旧 `failed` 或旧 `partial_failed`。
- 只补图接口必须要求 `confirm_text_visible=true`，并继续复用 `REPORT_TRIGGER_TOKEN`。
- 2026-08-22 恢复不得重新抓取、不得重新 ETL、不得再发文字，只能新增一张热力图。
- 不修改 `migrations/006_add_daily_job_snapshots.sql`；新建可重复执行的 Migration 007。
- 不暴露 `.env`、Bot Token、Chat ID、代理订阅、Cookie 或真实岗位快照。
- 保留工作区现有未提交文档；未经用户明确授权不执行任何 `git commit` 或 `git push`。

---

### Task 1: Telegram 单次投递与结果不确定异常

**Files:**
- Modify: `src/jobflow/channels/telegram.py`
- Modify: `tests/channels/test_telegram.py`

**Interfaces:**
- Produces: `TelegramDeliveryUncertain(message: str, attempts: int = 1)`。
- Preserves: `TelegramDeliveryError` 表示明确失败，`TelegramReceipt` 表示取得明确成功回执。
- Preserves: 其他旧调用仍按自己的 `max_attempts` 重试；多关键词服务将在 Task 3 固定传 `max_attempts=1`，因此本功能的文字和图片不会重试。

- [ ] **Step 1: 写出超时、5xx 和损坏成功回执的失败测试**

在 `tests/channels/test_telegram.py` 导入 `TelegramDeliveryUncertain`，并将旧的“超时后成功”和“5xx 重试三次”测试替换为：

```python
@pytest.mark.parametrize(
    "failure",
    [
        requests.Timeout("secret"),
        requests.ConnectionError("secret"),
    ],
)
def test_network_result_uncertain_is_not_retried(failure) -> None:
    post = Mock(side_effect=failure)

    with pytest.raises(TelegramDeliveryUncertain) as exc_info:
        send_telegram_text(
            "报告",
            bot_token="secret-bot-token",
            chat_id="1",
            post=post,
            sleep=Mock(),
            max_attempts=1,
        )

    assert post.call_count == 1
    assert exc_info.value.attempts == 1
    assert "secret" not in str(exc_info.value)


def test_server_error_is_uncertain_and_not_retried() -> None:
    post = Mock(return_value=response(503))

    with pytest.raises(TelegramDeliveryUncertain):
        send_telegram_photo(
            PNG_BYTES,
            bot_token="bot-token",
            chat_id="1",
            post=post,
            sleep=Mock(),
            max_attempts=1,
        )

    post.assert_called_once()


def test_malformed_success_payload_is_uncertain() -> None:
    post = Mock(return_value=response(payload={"ok": True, "result": {}}))

    with pytest.raises(TelegramDeliveryUncertain):
        send_telegram_text(
            "报告",
            bot_token="bot-token",
            chat_id="1",
            post=post,
            sleep=Mock(),
            max_attempts=1,
        )
```

- [ ] **Step 2: 运行定向测试，确认旧实现失败**

Run:

```powershell
conda run -n jobflow python -m pytest tests/channels/test_telegram.py -q
```

Expected: FAIL，原因包括无法导入 `TelegramDeliveryUncertain`，以及旧实现把超时/5xx 包装成 `TelegramDeliveryError`。

- [ ] **Step 3: 增加异常类型并收紧 `_request_telegram` 分类**

在 `TelegramDeliveryError` 后增加：

```python
class TelegramDeliveryUncertain(Exception):
    def __init__(self, message: str, *, attempts: int = 1) -> None:
        super().__init__(message)
        self.attempts = attempts
```

将 `_request_telegram()` 的请求循环改为以下判定；明确 4xx 不重试，5xx 和网络中断最终变成不确定，只有 Telegram 明确返回 `ok=false` 才是明确失败。为避免扩大本次改动，旧调用仍可通过大于 1 的 `max_attempts` 保留历史重试；Task 3 的多关键词日报固定传 1：

```python
def _request_telegram(
    *,
    request: Callable[[], object],
    max_attempts: int,
    sleep: Callable[[int], object],
) -> TelegramReceipt:
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    for attempt in range(1, max_attempts + 1):
        try:
            response = request()
        except Exception:
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryUncertain(
                "Telegram delivery result is uncertain", attempts=attempt
            ) from None

        if response.status_code >= 500:
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryUncertain(
                "Telegram delivery result is uncertain", attempts=attempt
            )
        if 400 <= response.status_code < 500:
            raise TelegramDeliveryError("Telegram request rejected", attempts=attempt)

        try:
            response.raise_for_status()
            payload = response.json()
        except Exception:
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryUncertain(
                "Telegram delivery result is uncertain", attempts=attempt
            ) from None

        if isinstance(payload, dict) and payload.get("ok") is False:
            raise TelegramDeliveryError("Telegram rejected message", attempts=attempt)
        message_id = (
            payload.get("result", {}).get("message_id")
            if isinstance(payload, dict)
            else None
        )
        if not isinstance(message_id, int) or message_id <= 0:
            if attempt < max_attempts:
                sleep(attempt)
                continue
            raise TelegramDeliveryUncertain(
                "Telegram delivery result is uncertain", attempts=attempt
            )
        return TelegramReceipt(message_id=message_id, attempts=attempt)

    raise TelegramDeliveryUncertain(
        "Telegram delivery result is uncertain", attempts=max_attempts
    )
```

保留 `sleep` 和 `max_attempts` 参数是为了不破坏既有调用签名；多关键词日报通过 `max_attempts=1` 关闭结果不确定故障的自动重试。

- [ ] **Step 4: 运行 Telegram 通道测试**

Run:

```powershell
conda run -n jobflow python -m pytest tests/channels/test_telegram.py -q
```

Expected: PASS；超时、断线、5xx 和损坏回执的 `post.call_count` 均为 1。

- [ ] **Step 5: 用户授权后建立独立提交**

```powershell
git add src/jobflow/channels/telegram.py tests/channels/test_telegram.py
git commit -m "fix: 区分 Telegram 明确失败与投递结果不确定"
```

---

### Task 2: Migration 007 与数据库状态转换原语

**Files:**
- Create: `migrations/007_add_uncertain_report_delivery_states.sql`
- Modify: `src/jobflow/db/snapshots.py`
- Modify: `tests/db/test_snapshot_migration.py`
- Modify: `tests/db/test_snapshots.py`

**Interfaces:**
- Produces: `get_deliveries_for_update(connection, snapshot_ids) -> tuple[ReportDelivery, ...]`。
- Produces: `record_text_sending`、`record_photo_sending`、`record_text_failed`、`record_photo_failed`、`record_text_uncertain`、`record_photo_uncertain`、`record_recovered_photo_sent`。
- Preserves: 旧的 `record_text_failure` / `record_photo_failure`，供单关键词旧流程兼容使用。

- [ ] **Step 1: 为 Migration 007 写契约测试**

在 `tests/db/test_snapshot_migration.py` 增加：

```python
def test_uncertain_delivery_migration_is_idempotent_and_complete() -> None:
    migration_path = Path("migrations/007_add_uncertain_report_delivery_states.sql")
    sql = migration_path.read_text(encoding="utf-8")
    normalized = " ".join(sql.split())

    for status in (
        "text_sending",
        "text_failed",
        "text_uncertain",
        "photo_sending",
        "photo_failed",
        "photo_uncertain",
        "completed_text_uncertain",
    ):
        assert f"'{status}'" in normalized
    assert "DROP CONSTRAINT IF EXISTS report_deliveries_status_check" in normalized
    assert "DROP CONSTRAINT IF EXISTS report_deliveries_state_check" in normalized
    assert "ADD CONSTRAINT report_deliveries_status_check" in normalized
    assert "ADD CONSTRAINT report_deliveries_state_check" in normalized
    assert "completed_text_uncertain" in normalized
    assert "text_message_id IS NULL" in normalized
    assert "photo_message_id IS NOT NULL" in normalized
```

- [ ] **Step 2: 运行 Migration 测试，确认文件缺失**

Run:

```powershell
conda run -n jobflow python -m pytest tests/db/test_snapshot_migration.py -q
```

Expected: FAIL at `read_text()` because Migration 007 does not exist。

- [ ] **Step 3: 新建可重复执行的 Migration 007**

创建 `migrations/007_add_uncertain_report_delivery_states.sql`：

```sql
ALTER TABLE ops.report_deliveries
    DROP CONSTRAINT IF EXISTS report_deliveries_status_check,
    DROP CONSTRAINT IF EXISTS report_deliveries_state_check;

ALTER TABLE ops.report_deliveries
    ADD CONSTRAINT report_deliveries_status_check CHECK (
        status IN (
            'pending', 'text_sending', 'text_sent', 'text_failed',
            'text_uncertain', 'photo_sending', 'photo_failed',
            'photo_uncertain', 'completed', 'completed_text_uncertain',
            'failed', 'partial_failed'
        )
    ),
    ADD CONSTRAINT report_deliveries_state_check CHECK (
        (status IN ('pending', 'text_sending', 'text_failed', 'text_uncertain', 'failed')
         AND text_message_id IS NULL AND photo_message_id IS NULL)
        OR
        (status IN ('text_sent', 'partial_failed')
         AND text_message_id IS NOT NULL AND photo_message_id IS NULL)
        OR
        (status IN ('photo_sending', 'photo_failed', 'photo_uncertain')
         AND photo_message_id IS NULL)
        OR
        (status = 'completed'
         AND text_message_id IS NOT NULL AND photo_message_id IS NOT NULL)
        OR
        (status = 'completed_text_uncertain'
         AND text_message_id IS NULL AND photo_message_id IS NOT NULL)
    );
```

- [ ] **Step 4: 为行锁和新转换函数写失败测试**

在 `tests/db/test_snapshots.py` 增加针对以下行为的测试：

```python
def test_get_deliveries_for_update_locks_exact_group() -> None:
    connection = ReadConnection(
        [
            (11, "pending", None, None, 0, 0, None),
            (12, "pending", None, None, 0, 0, None),
        ]
    )

    result = get_deliveries_for_update(connection, [12, 11])

    sql, params = connection.cursor_instance.executed[0]
    assert "FOR UPDATE" in sql
    assert "ORDER BY snapshot_id" in sql
    assert params == ([11, 12],)
    assert [item.snapshot_id for item in result] == [11, 12]


@pytest.mark.parametrize(
    ("transition", "status", "attempt_column"),
    [
        (record_text_sending, "text_sending", "text_attempts = text_attempts + 1"),
        (record_photo_sending, "photo_sending", "photo_attempts = photo_attempts + 1"),
    ],
)
def test_sending_transition_preclaims_before_network(
    transition, status: str, attempt_column: str
) -> None:
    connection = ReadConnection([])

    transition(connection, 17)

    sql, params = connection.cursor_instance.executed[0]
    assert attempt_column in " ".join(sql.split())
    assert params == (status, None, 17)


def test_recovered_photo_can_preserve_or_omit_text_receipt() -> None:
    connection = ReadConnection([])

    record_recovered_photo_sent(
        connection,
        17,
        message_id=202,
        attempts=1,
        text_receipt_known=False,
    )

    _sql, params = connection.cursor_instance.executed[0]
    assert params[0] == "completed_text_uncertain"
```

- [ ] **Step 5: 实现行锁读取与状态函数**

在 `src/jobflow/db/snapshots.py` 中复用 `ReportDelivery` 映射，增加：

```python
def get_deliveries_for_update(
    connection, snapshot_ids: list[int]
) -> tuple[ReportDelivery, ...]:
    normalized = sorted(set(snapshot_ids))
    if not normalized or len(normalized) != len(snapshot_ids):
        raise ValueError("snapshot_ids must be non-empty and unique")
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT snapshot_id, status, text_message_id, photo_message_id,
               text_attempts, photo_attempts, last_error_type
        FROM ops.report_deliveries
        WHERE snapshot_id = ANY(%s)
        ORDER BY snapshot_id
        FOR UPDATE
        """,
        (normalized,),
    )
    deliveries = tuple(ReportDelivery(*row) for row in cursor.fetchall())
    if [item.snapshot_id for item in deliveries] != normalized:
        raise ValueError("delivery group is incomplete")
    return deliveries


def _record_sending(connection, snapshot_id: int, *, status: str, stage: str) -> None:
    if stage not in {"text", "photo"}:
        raise ValueError("unsupported delivery stage")
    attempts_column = f"{stage}_attempts"
    cursor = connection.cursor()
    cursor.execute(
        f"""
        UPDATE ops.report_deliveries
        SET status = %s,
            {attempts_column} = {attempts_column} + 1,
            last_error_type = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE snapshot_id = %s
        """,
        (status, None, snapshot_id),
    )


def record_text_sending(connection, snapshot_id: int) -> None:
    _record_sending(connection, snapshot_id, status="text_sending", stage="text")


def record_photo_sending(connection, snapshot_id: int) -> None:
    _record_sending(connection, snapshot_id, status="photo_sending", stage="photo")
```

用现有 `_update_delivery()` 增加四个明确结果函数，状态分别为 `text_failed`、`photo_failed`、`text_uncertain`、`photo_uncertain`；它们不写 message ID，尝试次数固定传入 `1`。增加补图成功函数：

```python
def record_recovered_photo_sent(
    connection,
    snapshot_id: int,
    *,
    message_id: int,
    attempts: int,
    text_receipt_known: bool,
) -> None:
    _update_delivery(
        connection,
        snapshot_id,
        status="completed" if text_receipt_known else "completed_text_uncertain",
        message_column="photo_message_id",
        message_id=message_id,
        attempts_column="photo_attempts",
        attempts=attempts,
        error_type=None,
    )
```

- [ ] **Step 6: 运行 DB 单元测试与 Migration 解析测试**

Run:

```powershell
conda run -n jobflow python -m pytest tests/db/test_snapshots.py tests/db/test_snapshot_migration.py -q
```

Expected: PASS；SQL 测试能看到 `FOR UPDATE`，Migration 007 包含全部状态且第二次执行仍可先删除再重建约束。

- [ ] **Step 7: 用户授权后建立独立提交**

```powershell
git add migrations/007_add_uncertain_report_delivery_states.sql src/jobflow/db/snapshots.py tests/db/test_snapshot_migration.py tests/db/test_snapshots.py
git commit -m "feat: 增加日报不确定投递状态机"
```

---

### Task 3: 多关键词普通发送的预占与停止重试

**Files:**
- Modify: `src/jobflow/reports/multi_keyword_service.py`
- Modify: `tests/reports/test_multi_keyword_service.py`

**Interfaces:**
- Consumes: Task 1 的 `TelegramDeliveryUncertain`。
- Consumes: Task 2 的行锁和状态转换函数。
- Produces: `send_multi_keyword_report()` 只从全组 `pending` 开始发送；完成状态返回 `already_sent`；其他状态抛出 `MultiKeywordDeliveryStateError`。

- [ ] **Step 1: 写预占、超时停止和不可重发测试**

扩展测试夹具，使 `get_deliveries_for_update` 返回指定状态；增加：

```python
def test_text_is_preclaimed_and_committed_before_sender(monkeypatch) -> None:
    connection = arrange(monkeypatch)
    observed_commits: list[int] = []

    def text_sender(_text: str) -> TelegramReceipt:
        observed_commits.append(connection.commit.call_count)
        return TelegramReceipt(101, 1)

    multi_keyword_service.send_multi_keyword_report(
        connection,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
        text_sender=text_sender,
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert observed_commits == [1]
    assert multi_keyword_service.record_text_sending.call_count == 4
    assert multi_keyword_service.record_photo_sending.call_count == 4


def test_text_timeout_becomes_uncertain_and_never_calls_photo(monkeypatch) -> None:
    connection = arrange(monkeypatch)
    text_sender = Mock(side_effect=TelegramDeliveryUncertain("hidden", attempts=1))
    photo_sender = Mock()

    with pytest.raises(TelegramDeliveryUncertain):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=text_sender,
            photo_sender=photo_sender,
        )

    text_sender.assert_called_once()
    photo_sender.assert_not_called()
    assert multi_keyword_service.record_text_uncertain.call_count == 4


@pytest.mark.parametrize(
    "blocked_status",
    [
        "text_sending", "text_failed", "text_uncertain", "photo_sending",
        "photo_failed", "photo_uncertain", "failed", "partial_failed",
    ],
)
def test_ordinary_send_never_retries_blocked_stage(monkeypatch, blocked_status) -> None:
    connection = arrange(monkeypatch, delivery_status=blocked_status)
    text_sender = Mock()
    photo_sender = Mock()

    with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
        multi_keyword_service.send_multi_keyword_report(
            connection,
            snapshot_date=REPORT_DATE,
            keywords=KEYWORDS,
            text_sender=text_sender,
            photo_sender=photo_sender,
        )

    text_sender.assert_not_called()
    photo_sender.assert_not_called()
```

- [ ] **Step 2: 运行服务测试，确认旧逻辑仍会把 `failed` 当作 pending**

Run:

```powershell
conda run -n jobflow python -m pytest tests/reports/test_multi_keyword_service.py -q
```

Expected: FAIL；旧 `_delivery_phase()` 允许 `failed` 重发，且发送前没有 `*_sending` 预占提交。

- [ ] **Step 3: 实现严格同状态判定和普通发送状态机**

把 `_delivery_phase()` 改为只接受四条记录完全同状态。`completed` 和 `completed_text_uncertain` 都映射到完成；其他非 `pending` 状态不进入发送器：

```python
def _delivery_phase(
    deliveries: Sequence[ReportDelivery],
) -> tuple[str, int | None, int | None]:
    statuses = {delivery.status for delivery in deliveries}
    if len(statuses) != 1:
        raise MultiKeywordDeliveryStateError("keyword deliveries use different stages")
    status = next(iter(statuses))
    text_ids = [delivery.text_message_id for delivery in deliveries]
    photo_ids = [delivery.photo_message_id for delivery in deliveries]
    if status == "pending":
        if any(value is not None for value in (*text_ids, *photo_ids)):
            raise MultiKeywordDeliveryStateError("pending delivery contains message ids")
        return "pending", None, None
    if status == "completed":
        return (
            "completed",
            _single_message_id(text_ids, field="text message ids"),
            _single_message_id(photo_ids, field="photo message ids"),
        )
    if status == "completed_text_uncertain":
        if any(value is not None for value in text_ids):
            raise MultiKeywordDeliveryStateError("uncertain text contains message id")
        return (
            "completed",
            None,
            _single_message_id(photo_ids, field="photo message ids"),
        )
    raise MultiKeywordDeliveryStateError(f"delivery stage requires manual action: {status}")
```

普通发送流程按以下顺序实现：

```text
加载并校验快照
→ 在无数据库锁时构建文字和图片
→ FOR UPDATE 读取四条投递记录
→ 只允许 pending / completed
→ pending 时写四条 text_sending 并 commit
→ 构建文字和图片
→ text_sender 仅调用一次
→ 明确失败写 text_failed；不确定写 text_uncertain
→ 成功写 text_sent 并 commit
→ 再次 FOR UPDATE 并确认四条均为 text_sent
→ 写 photo_sending 并 commit
→ photo_sender 仅调用一次
→ 明确失败写 photo_failed；不确定写 photo_uncertain
→ 成功写 completed 并 commit
```

默认发送器改为 `None`，函数内生成固定单次调用包装：

```python
selected_text_sender = text_sender or (
    lambda value: send_telegram_text(value, max_attempts=1)
)
selected_photo_sender = photo_sender or (
    lambda value: send_telegram_photo(value, max_attempts=1)
)
```

不要在 `selected_text_sender()` 或 `selected_photo_sender()` 执行期间保留未提交事务；每次 `*_sending` 后必须先 `connection.commit()`。

- [ ] **Step 4: 增加模拟双请求竞争测试**

在第一个请求已提交 `text_sending`、刚进入 sender 的窗口内触发第二个请求。第二个请求读取到 `text_sending` 后必须退出，两个请求共享同一个 sender 计数器：

```python
def test_second_request_cannot_send_after_first_preclaim(monkeypatch) -> None:
    first = arrange(monkeypatch, delivery_status="pending")
    second = Mock()
    multi_keyword_service.get_deliveries_for_update.side_effect = [
        tuple(delivery(11 + index, "pending") for index in range(4)),
        tuple(delivery(11 + index, "text_sending") for index in range(4)),
        tuple(delivery(11 + index, "text_sent", text_message_id=101) for index in range(4)),
    ]

    sender_calls = 0

    def shared_sender(_text: str) -> TelegramReceipt:
        nonlocal sender_calls
        sender_calls += 1
        with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
            multi_keyword_service.send_multi_keyword_report(
                second,
                snapshot_date=REPORT_DATE,
                keywords=KEYWORDS,
                text_sender=shared_sender,
                photo_sender=Mock(),
            )
        return TelegramReceipt(101, 1)

    multi_keyword_service.send_multi_keyword_report(
        first,
        snapshot_date=REPORT_DATE,
        keywords=KEYWORDS,
        text_sender=shared_sender,
        photo_sender=Mock(return_value=TelegramReceipt(202, 1)),
    )

    assert sender_calls == 1
```

实现时应把竞争检查拆成“锁定并预占”的小函数，使测试能分别模拟第一个请求获得发送权、第二个请求看见已预占状态。验收重点是两个调用合计 `sender.call_count == 1`。

- [ ] **Step 5: 运行多关键词服务测试**

Run:

```powershell
conda run -n jobflow python -m pytest tests/reports/test_multi_keyword_service.py -q
```

Expected: PASS；旧的 `partial_failed` 自动补图测试应删除，因为普通接口不再允许该恢复路径。

- [ ] **Step 6: 用户授权后建立独立提交**

```powershell
git add src/jobflow/reports/multi_keyword_service.py tests/reports/test_multi_keyword_service.py
git commit -m "fix: 防止多关键词日报超时后重复发送"
```

---

### Task 4: 人工确认后的只补图服务与状态输出

**Files:**
- Modify: `src/jobflow/reports/multi_keyword_service.py`
- Modify: `tests/reports/test_multi_keyword_service.py`

**Interfaces:**
- Produces: `recover_multi_keyword_report_photo(connection, *, snapshot_date, confirm_text_visible, keywords=DAILY_KEYWORDS, photo_sender=None) -> dict[str, object]`。
- Produces: 状态结果统一包含 `manual_action_required`。
- Recovery input: 全组 `text_uncertain`；带 `last_error_type` 的旧 `failed`；已有同一文字 ID 的旧 `partial_failed`。

- [ ] **Step 1: 写恢复服务的保护测试**

增加以下断言组：

```python
def test_recovery_requires_explicit_visible_confirmation(monkeypatch) -> None:
    connection = arrange(monkeypatch, delivery_status="text_uncertain")
    photo_sender = Mock()

    with pytest.raises(multi_keyword_service.MultiKeywordDeliveryStateError):
        multi_keyword_service.recover_multi_keyword_report_photo(
            connection,
            snapshot_date=REPORT_DATE,
            confirm_text_visible=False,
            keywords=KEYWORDS,
            photo_sender=photo_sender,
        )

    photo_sender.assert_not_called()


def test_recovery_sends_only_photo_once(monkeypatch) -> None:
    connection = arrange(monkeypatch, delivery_status="text_uncertain")
    photo_sender = Mock(return_value=TelegramReceipt(202, 1))

    result = multi_keyword_service.recover_multi_keyword_report_photo(
        connection,
        snapshot_date=REPORT_DATE,
        confirm_text_visible=True,
        keywords=KEYWORDS,
        photo_sender=photo_sender,
    )

    photo_sender.assert_called_once_with(b"heatmap")
    assert result["status"] == "sent"
    assert result["photo_message_id"] == 202
    assert multi_keyword_service.record_text_sending.call_count == 0
    assert multi_keyword_service.record_recovered_photo_sent.call_count == 4


def test_recovery_photo_timeout_stops_without_retry(monkeypatch) -> None:
    connection = arrange(monkeypatch, delivery_status="text_uncertain")
    photo_sender = Mock(side_effect=TelegramDeliveryUncertain("hidden", attempts=1))

    with pytest.raises(TelegramDeliveryUncertain):
        multi_keyword_service.recover_multi_keyword_report_photo(
            connection,
            snapshot_date=REPORT_DATE,
            confirm_text_visible=True,
            keywords=KEYWORDS,
            photo_sender=photo_sender,
        )

    photo_sender.assert_called_once()
    assert multi_keyword_service.record_photo_uncertain.call_count == 4
```

- [ ] **Step 2: 实现恢复资格检查**

新增私有函数，要求四条记录状态一致：

```python
def _recovery_text_receipt_known(deliveries: Sequence[ReportDelivery]) -> bool:
    statuses = {item.status for item in deliveries}
    if len(statuses) != 1:
        raise MultiKeywordDeliveryStateError("keyword deliveries use different stages")
    status = next(iter(statuses))
    if status == "text_uncertain":
        if any(item.text_message_id is not None for item in deliveries):
            raise MultiKeywordDeliveryStateError("uncertain text contains message id")
        return False
    if status == "failed":
        if not all((item.last_error_type or "").startswith("telegram_") for item in deliveries):
            raise MultiKeywordDeliveryStateError("legacy failure has no Telegram evidence")
        return False
    if status == "partial_failed":
        _single_message_id(
            [item.text_message_id for item in deliveries],
            field="text message ids",
        )
        return True
    raise MultiKeywordDeliveryStateError("delivery stage cannot recover photo")
```

- [ ] **Step 3: 实现只补图流程**

`recover_multi_keyword_report_photo()` 执行：显式确认 → 加载四份快照 → 校验同范围 → 构建趋势和图片 → 行锁读取并再次校验恢复资格 → 写四条 `photo_sending` 并 commit → 单次发图 → 写明确/不确定结果。函数中不得导入或调用 `send_telegram_text`。

成功返回：

```python
return {
    "status": "sent",
    "snapshot_ids": snapshot_ids,
    "photo_message_id": photo_receipt.message_id,
    "text_receipt_known": text_receipt_known,
}
```

- [ ] **Step 4: 扩展状态接口**

`get_multi_keyword_report_status()` 的正常结果增加：

```python
manual_states = {
    "text_sending", "text_failed", "text_uncertain",
    "photo_sending", "photo_failed", "photo_uncertain",
    "failed", "partial_failed",
}
return {
    "status": phase,
    "snapshot_date": snapshot_date.isoformat(),
    "keywords": list(normalized),
    "text_sent": text_message_id is not None,
    "photo_sent": photo_message_id is not None,
    "manual_action_required": phase in manual_states,
}
```

状态读取不能复用只接受可发送状态的 `_delivery_phase()`；增加只校验“四条同状态和 ID 组合”的读取函数，确保 `text_uncertain` 能正常返回而不是 503。

- [ ] **Step 5: 运行服务测试**

Run:

```powershell
conda run -n jobflow python -m pytest tests/reports/test_multi_keyword_service.py -q
```

Expected: PASS；恢复测试确认文字发送器调用数为 0、图片调用数为 1。

- [ ] **Step 6: 用户授权后建立独立提交**

```powershell
git add src/jobflow/reports/multi_keyword_service.py tests/reports/test_multi_keyword_service.py
git commit -m "feat: 增加 Telegram 日报只补图恢复"
```

---

### Task 5: FastAPI 恢复入口与业务错误映射

**Files:**
- Modify: `src/jobflow/api/reports.py`
- Modify: `tests/api/test_reports.py`

**Interfaces:**
- Produces: `POST /reports/daily/multi/recover-photo?snapshot_date=YYYY-MM-DD&confirm_text_visible=true`。
- Authentication: `Authorization: Bearer <REPORT_TRIGGER_TOKEN>`。
- Error mapping: 恢复确认/状态冲突为 409；Telegram 明确失败或结果不确定为 502；缺配置为 503。

- [ ] **Step 1: 写 API 鉴权、确认参数和错误映射测试**

增加 dependency getter：

```python
def get_multi_daily_photo_recoverer():
    return recover_multi_keyword_report_photo
```

在 API 测试中覆盖：无 Token 时数据库 provider 不调用；`confirm_text_visible=false` 返回 409；`true` 时把日期和布尔值传给服务；`MultiKeywordDeliveryStateError` 返回 409；`TelegramDeliveryUncertain` 返回 502 且响应不包含异常原文。

关键成功测试：

```python
def test_multi_photo_recovery_forwards_explicit_confirmation(monkeypatch) -> None:
    recoverer = Mock(return_value={"status": "sent", "photo_message_id": 202})
    connection = Mock()
    client, app = multi_recovery_client(
        monkeypatch, recoverer, connection_provider=lambda: connection
    )
    try:
        response = client.post(
            "/reports/daily/multi/recover-photo"
            "?snapshot_date=2026-08-22&confirm_text_visible=true",
            headers={"Authorization": "Bearer test-trigger-token"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    recoverer.assert_called_once_with(
        connection,
        snapshot_date=date(2026, 8, 22),
        confirm_text_visible=True,
    )
```

- [ ] **Step 2: 运行 API 测试，确认路由尚不存在**

Run:

```powershell
conda run -n jobflow python -m pytest tests/api/test_reports.py -q
```

Expected: FAIL with HTTP 404 or missing dependency getter。

- [ ] **Step 3: 实现恢复路由和普通发送 409 映射**

普通 `/daily/multi/send` 捕获 `MultiKeywordDeliveryStateError` 并返回：

```python
raise HTTPException(status_code=409, detail="report delivery requires manual action")
```

新增：

```python
@router.post("/daily/multi/recover-photo", dependencies=[Depends(require_report_token)])
def recover_multi_daily_snapshot_photo(
    snapshot_date: date,
    confirm_text_visible: bool = False,
    connection=Depends(get_connection),
    photo_recoverer=Depends(get_multi_daily_photo_recoverer),
):
    if not confirm_text_visible:
        raise HTTPException(status_code=409, detail="visible text confirmation required")
    try:
        return photo_recoverer(
            connection,
            snapshot_date=snapshot_date,
            confirm_text_visible=True,
        )
    except MultiKeywordSnapshotMissing as exc:
        raise HTTPException(status_code=409, detail="daily snapshots incomplete") from exc
    except MultiKeywordDeliveryStateError as exc:
        raise HTTPException(
            status_code=409,
            detail="report delivery requires manual action",
        ) from exc
    except (TelegramDeliveryError, TelegramDeliveryUncertain) as exc:
        raise HTTPException(status_code=502, detail="report delivery failed") from exc
    except TelegramConfigurationError as exc:
        raise HTTPException(status_code=503, detail="report service unavailable") from exc
```

- [ ] **Step 4: 运行 API 测试**

Run:

```powershell
conda run -n jobflow python -m pytest tests/api/test_reports.py -q
```

Expected: PASS；所有错误正文均为固定业务文案，不泄漏 Token 或 Telegram 返回详情。

- [ ] **Step 5: 用户授权后建立独立提交**

```powershell
git add src/jobflow/api/reports.py tests/api/test_reports.py
git commit -m "feat: 开放受保护的日报只补图接口"
```

---

### Task 6: 每日脚本超时与人工处理提示

**Files:**
- Modify: `ops/daily_update.sh`
- Modify: `tests/ops/test_daily_update_script.py`

**Interfaces:**
- Consumes: `/reports/daily/multi/send` 与 `/reports/daily/multi/status`。
- Produces: API 外层等待 120 秒；不确定/冲突时非零退出并提示人工检查；不执行第二次发送。

- [ ] **Step 1: 写脚本静态契约测试**

在 `tests/ops/test_daily_update_script.py` 增加：

```python
def test_daily_report_request_waits_for_single_safe_delivery() -> None:
    text = read_script()

    assert "urlopen(request, timeout=120)" in text
    assert text.count("/reports/daily/multi/send?snapshot_date=") == 1
    assert "/reports/daily/multi/status?snapshot_date=" in text
    assert "投递结果不确定，需要人工检查" in text
```

- [ ] **Step 2: 运行脚本测试，确认旧超时为 30 秒**

Run:

```powershell
conda run -n jobflow python -m pytest tests/ops/test_daily_update_script.py -q
```

Expected: FAIL because report `urlopen` still uses `timeout=30` and has no multi status fallback。

- [ ] **Step 3: 调整发送调用并只读查询最终状态**

仅把 `send_multi_keyword_report()` 内部 POST 的 timeout 改为 120；快照存在性查询可继续使用 30 秒。捕获 HTTPError/URLError/TimeoutError 后，使用相同 Token 对：

```text
GET http://127.0.0.1:8000/reports/daily/multi/status?snapshot_date=2026-08-22
```

执行一次只读查询。若响应的 `manual_action_required` 为 `true`，输出：

```text
合并日报投递结果不确定，需要人工检查 Telegram 与投递状态
```

随后 `SystemExit(1)`。不得再次 POST `/send`，不得调用 `/recover-photo`，不得回到抓取或 ETL 循环。

- [ ] **Step 4: 验证 Bash 语法和静态测试**

Run:

```powershell
conda run -n jobflow python -m pytest tests/ops/test_daily_update_script.py -q
wsl bash -n /mnt/e/Code/JobFlow/ops/daily_update.sh
```

Expected: pytest PASS；`bash -n` exit code 0 且无输出。

- [ ] **Step 5: 用户授权后建立独立提交**

```powershell
git add ops/daily_update.sh tests/ops/test_daily_update_script.py
git commit -m "fix: 完善日报不确定投递提示与等待时间"
```

---

### Task 7: 全量审查、Ubuntu 部署与 2026-08-22 只补图验收

**Files:**
- Modify after server acceptance: `README.md`
- Modify after server acceptance: `docs/project-handoff.md`
- Modify after server acceptance: `docs/ubuntu-deployment.md`
- Read only during recovery: `.env`

**Interfaces:**
- Produces: 本机回归证据、服务器恢复证据、恢复后的文档状态。
- Safety gate: Ubuntu `jobflow-daily-update.timer` 在新代码部署并验收前必须为 inactive。

- [ ] **Step 1: 确认服务器旧定时器已暂停**

在 Ubuntu 执行：

```bash
sudo systemctl stop jobflow-daily-update.timer
systemctl is-active jobflow-daily-update.timer
```

Expected:

```text
inactive
```

- [ ] **Step 2: 本机执行定向与非 PostgreSQL 全回归**

```powershell
conda run -n jobflow python -m pytest tests/channels/test_telegram.py tests/db/test_snapshots.py tests/db/test_snapshot_migration.py tests/reports/test_multi_keyword_service.py tests/api/test_reports.py tests/ops/test_daily_update_script.py -q
conda run -n jobflow python -m pytest tests --ignore=tests/integration -q
conda run -n jobflow python -m ruff check src tests
git diff --check
```

Expected: 全部 PASS；Ruff exit code 0；`git diff --check` 无错误。记录实际测试数，不沿用历史数字。

- [ ] **Step 3: 用户明确授权后提交并推送本次实现文件**

先运行 `git status --short`，只暂存 Tasks 1-6 的代码、Migration 和测试；不暂存 `.superpowers/`、真实数据、`.env`、订阅链接或其他无关文档。建议合并提交信息：

```powershell
git commit -m "fix: 防止 Telegram 超时重复发送并支持只补图"
git push origin main
```

- [ ] **Step 4: Ubuntu 拉取、构建、迁移和就绪检查**

```bash
cd <JOBFLOW_DIR>
git pull --ff-only origin main
docker compose build api etl
docker compose up -d db
docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < migrations/007_add_uncertain_report_delivery_states.sql
docker compose up -d --force-recreate api
docker compose ps
curl -fsS http://127.0.0.1:8000/ready
```

`<JOBFLOW_DIR>` 与现有 Ubuntu 部署文档保持一致，由维护者替换为服务器真实仓库目录；执行前用 `pwd` 确认当前路径。Expected: Migration exit code 0；API 容器 healthy；`/ready` 返回就绪成功。

- [ ] **Step 5: 只读核对 2026-08-22 四份记录**

在服务器数据库内执行只读 SQL，确认四个关键词都有快照，且投递记录仍为旧 `failed`、文字/图片 ID 均为空、错误类型为 Telegram 投递：

```sql
SELECT s.snapshot_date, s.search_keyword, d.status,
       d.text_message_id, d.photo_message_id,
       d.text_attempts, d.photo_attempts, d.last_error_type
FROM core.job_snapshots AS s
JOIN ops.report_deliveries AS d ON d.snapshot_id = s.id
WHERE s.snapshot_date = DATE '2026-08-22'
ORDER BY s.search_keyword;
```

Expected: 4 rows；不执行 UPDATE，不伪造 message ID。

- [ ] **Step 6: 由用户确认 Telegram 文字可见后只调用一次补图接口**

在 API 容器内读取已有环境变量，不在主机终端打印 Token：

```bash
docker compose exec -T api python - <<'PY'
import json
import os
import urllib.request

token = os.environ["REPORT_TRIGGER_TOKEN"]
request = urllib.request.Request(
    "http://127.0.0.1:8000/reports/daily/multi/recover-photo"
    "?snapshot_date=2026-08-22&confirm_text_visible=true",
    method="POST",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(request, timeout=120) as response:
    print(json.dumps(json.load(response), ensure_ascii=False))
PY
```

Expected: `status=sent`，返回一个正整数 `photo_message_id`。Telegram 只新增一张热力图，没有新增文字。

- [ ] **Step 7: 验证最终状态并重新启用正式定时器**

```bash
docker compose exec -T api python - <<'PY'
import json
import os
import urllib.request

token = os.environ["REPORT_TRIGGER_TOKEN"]
request = urllib.request.Request(
    "http://127.0.0.1:8000/reports/daily/multi/status?snapshot_date=2026-08-22",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(request, timeout=30) as response:
    print(json.dumps(json.load(response), ensure_ascii=False))
PY
sudo systemctl enable --now jobflow-daily-update.timer
systemctl is-active jobflow-daily-update.timer
systemctl list-timers jobflow-daily-update.timer --all
```

Expected: 状态为 `completed_text_uncertain`、`photo_sent=true`、`manual_action_required=false`；timer 为 `active`，并显示下一次 Asia/Shanghai 09:00 运行时间。

- [ ] **Step 8: 服务器验收后维护公开与个人文档**

在 `README.md` 和 `docs/ubuntu-deployment.md` 增加以下公开说明，所有个人值继续使用占位：

```text
Telegram Bot API 不提供客户端幂等键。JobFlow 在超时或响应中断时会停止自动重试，
并把投递标记为“结果不确定”，以避免重复刷屏。维护者确认文字已可见后，可以通过
受 Bearer Token 保护的 recover-photo 接口只补发图片。服务器定时任务、代理地址和
REPORT_TRIGGER_TOKEN 均需按部署环境配置，禁止提交真实凭据。
```

在 `docs/project-handoff.md` 记录实际 commit、Migration 007 执行结果、本机测试数、2026-08-22 补图结果和下一次 timer 时间。保留工作区已有文档改动，先查看 `git diff -- README.md docs/project-handoff.md docs/ubuntu-deployment.md` 再合并，不覆盖先前内容。

- [ ] **Step 9: 用户授权后提交文档，不混入业务代码**

```powershell
git add README.md docs/project-handoff.md docs/ubuntu-deployment.md
git commit -m "docs: 更新 Telegram 防重复与只补图维护说明"
git push origin main
```

知识库只在服务器真实验收完成后按既有 JobFlow 卡片和每日记录结构更新；不提前创建未完成日期的成果记录。
