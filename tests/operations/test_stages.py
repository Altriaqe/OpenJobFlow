from jobflow.operations.models import StageDefinition, StageEvidence, StageState
from jobflow.operations.stages import build_stage_snapshot, derive_stage_state


DEFINITION = StageDefinition("x", "测试", "目标", "验收")


def test_state_precedence():
    assert (
        derive_stage_state(DEFINITION, StageEvidence(error=True, accepted=True)) == StageState.ERROR
    )
    assert (
        derive_stage_state(DEFINITION, StageEvidence(observing=True, accepted=True))
        == StageState.OBSERVING
    )
    assert derive_stage_state(DEFINITION, StageEvidence(accepted=True)) == StageState.ACCEPTED
    assert derive_stage_state(DEFINITION, StageEvidence(implemented=True)) == StageState.COMPLETED
    assert derive_stage_state(DEFINITION, StageEvidence()) == StageState.NOT_STARTED


def test_snapshot_preserves_configuration_order():
    first = StageDefinition("first", "第一", "", "")
    second = StageDefinition("second", "第二", "", "")
    result = build_stage_snapshot([first, second], {"second": StageEvidence(implemented=True)})
    assert [item.definition.id for item in result] == ["first", "second"]
    assert result[1].state == StageState.COMPLETED
