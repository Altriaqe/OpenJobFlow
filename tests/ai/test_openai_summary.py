from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from jobflow.ai.openai_summary import (
    OpenAIConfigurationError,
    OpenAISummaryError,
    generate_city_report,
)


def test_generate_city_report_uses_only_aggregate_facts():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text="城市岗位报告")
    rows = [
        {"city": "Hangzhou", "job_count": 12},
        {"city": "Lanzhou", "job_count": 8},
    ]

    result = generate_city_report(rows, client=client, model="test-model")

    assert result == "城市岗位报告"
    call = client.responses.create.call_args.kwargs
    assert call["model"] == "test-model"
    assert "Hangzhou" in call["input"]
    assert "12" in call["input"]
    assert "Lanzhou" in call["input"]
    assert "8" in call["input"]
    assert "当前数据库" in call["instructions"]
    assert "不得编造" in call["instructions"]


def test_generate_city_report_requires_model(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(OpenAIConfigurationError, match="OPENAI_MODEL"):
        generate_city_report([{"city": "Hangzhou", "job_count": 12}], client=Mock())


def test_generate_city_report_rejects_empty_output():
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(output_text="   ")

    with pytest.raises(OpenAISummaryError, match="empty output"):
        generate_city_report(
            [{"city": "Hangzhou", "job_count": 12}],
            client=client,
            model="test-model",
        )


def test_generate_city_report_hides_provider_error():
    client = Mock()
    client.responses.create.side_effect = RuntimeError("secret provider detail")

    with pytest.raises(OpenAISummaryError, match="OpenAI request failed") as exc_info:
        generate_city_report(
            [{"city": "Hangzhou", "job_count": 12}],
            client=client,
            model="test-model",
        )

    assert "secret provider detail" not in str(exc_info.value)
