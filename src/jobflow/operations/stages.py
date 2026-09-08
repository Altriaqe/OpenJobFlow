"""根据运行证据计算阶段状态。"""

from collections.abc import Mapping, Sequence

from jobflow.operations.models import CheckResult, StageDefinition, StageEvidence, StageSnapshot, StageState


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


def stage_evidence(last_checks: Sequence[CheckResult]) -> dict[str, StageEvidence]:
    """将最近一次服务器检查结果转换为八个阶段的统一证据。"""
    # 查询按时间倒序；同名检查只保留最近一次，避免旧记录覆盖新状态。
    statuses = {}
    for item in last_checks:
        statuses.setdefault(item.name, item.status)
    evidence = {
        stage_id: StageEvidence()
        for stage_id in (
            "data_source",
            "collection",
            "etl",
            "postgres",
            "analytics_api",
            "reports",
            "telegram",
            "wechat",
        )
    }
    infrastructure_ok = statuses.get("postgres") == "succeeded"
    evidence["data_source"] = StageEvidence(implemented=True)
    evidence["collection"] = StageEvidence(
        implemented=True, accepted=statuses.get("boss_login") == "succeeded"
    )
    evidence["etl"] = StageEvidence(
        implemented=True, accepted=statuses.get("latest_etl") == "succeeded"
    )
    evidence["postgres"] = StageEvidence(implemented=True, accepted=infrastructure_ok)
    evidence["analytics_api"] = StageEvidence(
        implemented=True, accepted=statuses.get("ready") == "succeeded"
    )
    evidence["reports"] = StageEvidence(
        implemented=True, accepted=statuses.get("latest_etl") == "succeeded"
    )
    evidence["telegram"] = StageEvidence(
        implemented=True, accepted=statuses.get("telegram") == "succeeded"
    )
    evidence["wechat"] = StageEvidence(
        implemented=True, accepted=statuses.get("wechat") == "succeeded"
    )
    return evidence
