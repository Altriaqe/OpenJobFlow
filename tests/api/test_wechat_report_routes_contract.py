from pathlib import Path


def test_wechat_routes_are_token_protected_and_require_explicit_resend_confirmation():
    source = Path("src/jobflow/api/reports.py").read_text(encoding="utf-8")

    assert (
        '@router.post("/daily/multi/wechat/send", dependencies=[Depends(require_report_token)])'
        in source
    )
    assert (
        '@router.get("/daily/multi/wechat/status", dependencies=[Depends(require_report_token)])'
        in source
    )
    assert (
        '@router.post("/daily/multi/wechat/resend", dependencies=[Depends(require_report_token)])'
        in source
    )
    assert "confirm_not_received: bool = False" in source
