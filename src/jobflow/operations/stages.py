"""根据运行证据计算阶段状态。"""

from collections.abc import Mapping, Sequence

from jobflow.operations.models import StageDefinition, StageEvidence, StageSnapshot, StageState


def derive_stage_state(definition: StageDefinition, evidence: StageEvidence) -> StageState:
    del definition
    if evidence.error:
        return StageState.ERROR
    if evidence.observing:
        return StageState.OBSERVING
    if evidence.accepted:
        return StageState.ACCEPTED
    if evidence.implemented:
        return StageState.COMPLETED
    return StageState.NOT_STARTED


def build_stage_snapshot(
    definitions: Sequence[StageDefinition], evidence_by_stage: Mapping[str, StageEvidence]
) -> tuple[StageSnapshot, ...]:
    return tuple(
        StageSnapshot(
            definition,
            derive_stage_state(definition, evidence_by_stage.get(definition.id, StageEvidence())),
        )
        for definition in definitions
    )
