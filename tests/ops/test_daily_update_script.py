from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "daily_update.sh"


def read_script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_daily_update_script_exists_and_is_strict() -> None:
    text = read_script()

    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -Eeuo pipefail" in text
    assert "flock -n 9" in text
    assert 'boss_cdp_raw.py" --check' in text


def test_daily_update_uses_four_keywords_and_original_scope() -> None:
    text = read_script()

    assert 'KEYWORDS=("AI Agent" "Python开发" "Java开发" "数据分析")' in text
    assert 'CITIES=("上海" "北京" "杭州" "深圳")' in text
    assert "PAGES=3" in text
    assert 'for index in "${!KEYWORDS[@]}"' in text
    assert '--keyword "$keyword"' in text
    assert '--search-keyword "$keyword"' in text
    assert '--pages "$PAGES"' in text
    assert "--no-detail" in text


def test_daily_update_passes_exact_snapshot_scope_to_etl() -> None:
    text = read_script()

    assert '--snapshot-date "$SNAPSHOT_DATE"' in text
    assert '--search-keyword "$keyword"' in text
    assert "--cities" in text
    assert '--pages-per-city "$PAGES"' in text
    assert "--detail-mode no-detail" in text


def test_daily_update_checks_each_snapshot_and_sends_one_combined_report() -> None:
    text = read_script()

    status_position = text.index('if snapshot_exists "$SNAPSHOT_DATE" "$keyword"; then')
    capture_position = text.index('capture_keyword "$keyword" "$index"')
    etl_position = text.index("docker compose run --rm etl")
    final_send_position = text.rindex('send_multi_keyword_report "$SNAPSHOT_DATE"')

    assert status_position < capture_position
    assert etl_position < final_send_position
    assert "docker compose exec -T api python -" in text
    assert "/reports/daily/status?{query}" in text
    assert "/reports/daily/multi/send?snapshot_date=" in text
    assert text.count("/reports/daily/multi/send?snapshot_date=") == 1
    assert "/reports/cities/send?mode=query" not in text
    assert "exc.code == 404 else 1" in text
    assert 'payload.get("status") not in {"sent", "already_sent"}' in text
    assert "已存在快照，本关键词跳过抓取" in text


def test_daily_update_rejects_empty_city_and_deduplicates_job_identity() -> None:
    text = read_script()

    assert "if not jobs:" in text
    assert "返回 0 条岗位，整批停止" in text
    assert 'job.get("job_id", "")' in text
    assert "seen_job_ids = set()" in text
    assert "if job_id not in seen_job_ids:" in text
    assert "all_jobs.append(job)" in text


def test_daily_update_does_not_extract_or_print_trigger_token_on_host() -> None:
    text = read_script()

    assert "sed -n 's/^REPORT_TRIGGER_TOKEN=" not in text
    assert "source .env" not in text
    assert "set -x" not in text
    assert "REPORT_TRIGGER_TOKEN_VALUE" not in text


def test_daily_update_script_has_no_personal_absolute_paths() -> None:
    text = read_script()

    assert 'JOBFLOW_DIR="/home/' not in text
    assert "JOBFLOW_SCRAPER_DIR" in text
    assert "BASH_SOURCE[0]" in text


def test_daily_update_waits_for_api_before_snapshot_checks() -> None:
    text = read_script()

    assert 'API_READY_URL="http://127.0.0.1:8000/ready"' in text
    assert "API_READY_TIMEOUT_SECONDS=300" in text
    assert "API_READY_MAX_ATTEMPTS=60" in text
    assert "API_READY_RETRY_INTERVAL_SECONDS=5" in text
    assert "API_READY_REQUEST_TIMEOUT_SECONDS=3" in text
    assert "wait_for_api_ready()" in text
    assert "curl --fail --silent --output /dev/null" in text
    assert 'request_timeout="$API_READY_REQUEST_TIMEOUT_SECONDS"' in text
    assert '--max-time "$request_timeout"' in text

    function_position = text.index("wait_for_api_ready()")
    call_position = text.index("wait_for_api_ready\n")
    snapshot_position = text.index('if snapshot_exists "$SNAPSHOT_DATE" "$keyword"; then')

    assert function_position < call_position < snapshot_position
    assert 'echo "API 在 5 分钟内未就绪，每日任务停止" >&2' in text


def test_daily_report_request_waits_and_checks_uncertain_status_once() -> None:
    text = read_script()

    assert "urllib.request.urlopen(request, timeout=120)" in text
    assert text.count("/reports/daily/multi/send?snapshot_date=") == 1
    assert "/reports/daily/multi/status?snapshot_date=" in text
    assert "投递结果不确定，需要人工检查" in text


def test_daily_update_runs_telegram_and_wechat_in_parallel() -> None:
    text = read_script()

    assert 'send_multi_keyword_report "$SNAPSHOT_DATE" &' in text
    assert 'send_wechat_report "$SNAPSHOT_DATE" &' in text
    assert 'wait "$telegram_pid"' in text
    assert 'wait "$wechat_pid"' in text
    assert 'if [[ "$telegram_status" -ne 0 || "$wechat_status" -ne 0 ]]' in text
    assert "/reports/daily/multi/wechat/send?snapshot_date=" in text
    assert 'allowed = {"sent", "already_sent", "disabled"}' in text
