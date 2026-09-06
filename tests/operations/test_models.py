from pathlib import Path

import pytest

from jobflow.operations.models import StageState, load_stage_definitions


def test_platform_configuration_has_eight_ordered_stages():
    stages = load_stage_definitions(Path("config/platform_stages.yaml"))
    assert len(stages) == 8
    assert [stage.name for stage in stages] == [
        "数据源",
        "采集任务",
        "ETL 处理",
        "PostgreSQL 数据层",
        "数据分析 API",
        "报告生成",
        "Telegram 投放",
        "微信公众号投放",
    ]


def test_stage_states_are_fixed():
    assert {state.value for state in StageState} == {
        "未开始",
        "开发中",
        "已完成",
        "已验收",
        "观察中",
        "异常",
    }


def test_invalid_stage_configuration_is_rejected(tmp_path):
    path = tmp_path / "stages.yaml"
    path.write_text("stages: []", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly eight"):
        load_stage_definitions(path)
