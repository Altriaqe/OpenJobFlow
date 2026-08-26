"""报告发送编排层：连接分析查询、文字生成和 Telegram 渠道。"""

from jobflow.ai.openai_summary import generate_city_report
from jobflow.channels.telegram import send_telegram_text
from jobflow.db.analytics import list_city_job_counts
from jobflow.reports.query_report import build_query_report


def send_city_report(
    connection,
    *,
    mode: str = "query",
    summary_generator=generate_city_report,
    sender=None,
) -> dict[str, object]:
    if mode not in {"query", "ai"}:
        raise ValueError("unsupported report mode")

    sender = sender or send_telegram_text
    rows = list_city_job_counts(connection, limit=100)
    if not rows:
        return {"status": "skipped", "city_count": 0}

    report = build_query_report(rows) if mode == "query" else summary_generator(rows)
    sender(report)
    return {"status": "sent", "city_count": len(rows)}
