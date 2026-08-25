import json
import os

from openai import OpenAI


class OpenAIConfigurationError(Exception):
    pass


class OpenAISummaryError(Exception):
    pass


INSTRUCTIONS = """你是 JobFlow 招聘数据报告助手。
只根据输入的城市和岗位数量总结事实。
统计口径是当前数据库中的岗位数量，不代表历史趋势或完整市场规模。
不得编造薪资、技能、趋势、原因或输入中不存在的数字。
使用简洁中文输出适合企业微信群阅读的报告。"""


def generate_city_report(
    rows: list[dict[str, object]],
    *,
    client=None,
    model: str | None = None,
) -> str:
    selected_model = model or os.getenv("OPENAI_MODEL")
    if not selected_model:
        raise OpenAIConfigurationError("missing OPENAI_MODEL")

    openai_client = client or OpenAI()
    input_text = json.dumps(
        {"metric_scope": "当前数据库中的城市岗位数量", "cities": rows},
        ensure_ascii=False,
    )

    try:
        response = openai_client.responses.create(
            model=selected_model,
            instructions=INSTRUCTIONS,
            input=input_text,
        )
    except Exception as exc:
        raise OpenAISummaryError("OpenAI request failed") from exc

    report = response.output_text.strip()
    if not report:
        raise OpenAISummaryError("OpenAI returned empty output")

    return report
