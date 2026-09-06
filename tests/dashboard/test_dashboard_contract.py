from pathlib import Path


APP = Path("src/jobflow/dashboard/app.py").read_text(encoding="utf-8")


def test_dashboard_exposes_required_areas_and_stage_names():
    assert '"平台总览"' in APP
    assert '"运行中心"' in APP
    assert '"投放中心"' in APP
    for name in (
        "数据源",
        "采集任务",
        "ETL 处理",
        "PostgreSQL 数据层",
        "数据分析 API",
        "报告生成",
        "Telegram 投放",
        "微信公众号投放",
    ):
        assert name in Path("config/platform_stages.yaml").read_text(encoding="utf-8")


def test_dashboard_does_not_contain_direct_sql_or_shell_execution():
    assert "cursor(" not in APP
    assert "requests." not in APP
    assert "subprocess.run" in APP
    assert "[script]" in APP
    assert "claim_delivery_action" in APP
    assert "finish_delivery_action" in APP
