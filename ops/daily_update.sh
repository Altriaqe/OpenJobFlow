#!/usr/bin/env bash

set -Eeuo pipefail

# 每日入口只负责顺序编排：抓取、ETL、生成日报，再并行触发各消息渠道。
# 业务统计和投递幂等由 API/数据库负责，避免 Shell 复制业务规则。

# 同一时间只允许一个每日更新任务运行。
LOCK_FILE="/tmp/jobflow-daily-update.lock"
exec 9>"$LOCK_FILE"

if ! flock -n 9; then
    echo "已有 JobFlow 每日更新任务正在运行，本次跳过"
    exit 0
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
JOBFLOW_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
SCRAPER_DIR="${JOBFLOW_SCRAPER_DIR:-$(dirname "$JOBFLOW_DIR")/boss-zhipin-scraper}"
PYTHON="${SCRAPER_DIR}/.venv/bin/python"
INBOX_DIR="${JOBFLOW_DIR}/data/raw/inbox"
API_READY_URL="http://127.0.0.1:8000/ready"
API_READY_TIMEOUT_SECONDS=300
API_READY_MAX_ATTEMPTS=60
API_READY_RETRY_INTERVAL_SECONDS=5
API_READY_REQUEST_TIMEOUT_SECONDS=3

export DISPLAY="${DISPLAY:-:99}"

KEYWORDS=("AI Agent" "Python开发" "Java开发" "数据分析")
CITIES=("上海" "北京" "杭州" "深圳")
PAGES=3
SNAPSHOT_DATE="$(date +%F)"
WORK_DIR="$(mktemp -d /tmp/jobflow-daily.XXXXXX)"

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

wait_for_api_ready() {
    local deadline=$((SECONDS + API_READY_TIMEOUT_SECONDS))
    local attempt
    local remaining
    local request_timeout
    local sleep_seconds

    echo "等待 JobFlow API 就绪"

    for ((attempt = 1; attempt <= API_READY_MAX_ATTEMPTS; attempt++)); do
        remaining=$((deadline - SECONDS))
        if ((remaining <= 0)); then
            break
        fi

        request_timeout="$API_READY_REQUEST_TIMEOUT_SECONDS"
        if ((remaining < request_timeout)); then
            request_timeout="$remaining"
        fi

        if curl --fail --silent --output /dev/null \
            --max-time "$request_timeout" \
            "$API_READY_URL"; then
            echo "JobFlow API 已就绪"
            return 0
        fi

        remaining=$((deadline - SECONDS))
        if ((remaining <= 0 || attempt == API_READY_MAX_ATTEMPTS)); then
            break
        fi

        sleep_seconds="$API_READY_RETRY_INTERVAL_SECONDS"
        if ((remaining < sleep_seconds)); then
            sleep_seconds="$remaining"
        fi
        sleep "$sleep_seconds"
    done

    echo "API 在 5 分钟内未就绪，每日任务停止" >&2
    return 1
}

snapshot_exists() {
    local snapshot_date="$1"
    local keyword="$2"

    docker compose exec -T api python - "$snapshot_date" "$keyword" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

token = os.getenv("REPORT_TRIGGER_TOKEN")
if not token:
    print("日报状态检查失败：缺少触发凭据", file=sys.stderr)
    raise SystemExit(1)

query = urllib.parse.urlencode(
    {"snapshot_date": sys.argv[1], "keyword": sys.argv[2]}
)
request = urllib.request.Request(
    f"http://127.0.0.1:8000/reports/daily/status?{query}",
    headers={"Authorization": f"Bearer {token}"},
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
except urllib.error.HTTPError as exc:
    raise SystemExit(10 if exc.code == 404 else 1) from None
except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
    raise SystemExit(1) from None

if not isinstance(payload, dict) or payload.get("snapshot_date") != sys.argv[1]:
    raise SystemExit(1)
raise SystemExit(0)
PY
}

send_multi_keyword_report() {
    local snapshot_date="$1"

    docker compose exec -T api python - "$snapshot_date" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

token = os.getenv("REPORT_TRIGGER_TOKEN")
if not token:
    print("合并日报接口调用失败：缺少触发凭据", file=sys.stderr)
    raise SystemExit(1)

snapshot_date = sys.argv[1]
request = urllib.request.Request(
    f"http://127.0.0.1:8000/reports/daily/multi/send?snapshot_date={snapshot_date}",
    method="POST",
    headers={"Authorization": f"Bearer {token}"},
)


def manual_action_required():
    status_request = urllib.request.Request(
        f"http://127.0.0.1:8000/reports/daily/multi/status?snapshot_date={snapshot_date}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(status_request, timeout=30) as response:
            status_payload = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False
    return (
        isinstance(status_payload, dict)
        and status_payload.get("manual_action_required") is True
    )


def stop_after_delivery_error(message):
    if manual_action_required():
        print("合并日报投递结果不确定，需要人工检查 Telegram 与投递状态", file=sys.stderr)
    else:
        print(message, file=sys.stderr)
    raise SystemExit(1)

try:
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
except urllib.error.HTTPError as exc:
    stop_after_delivery_error(f"合并日报接口调用失败：HTTP {exc.code}")
except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
    stop_after_delivery_error(f"合并日报接口调用失败：{type(exc).__name__}")

if not isinstance(payload, dict) or payload.get("status") not in {"sent", "already_sent"}:
    status = payload.get("status") if isinstance(payload, dict) else "invalid"
    print(f"合并日报接口调用失败：status={status}", file=sys.stderr)
    raise SystemExit(1)

print(f"合并日报投递状态：{payload.get('status')}")
PY
}

generate_wechat_article() {
    local snapshot_date="$1"

    docker compose exec -T api python - "$snapshot_date" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

token = os.getenv("REPORT_TRIGGER_TOKEN")
if not token:
    print("微信文章生成接口调用失败：缺少触发凭据", file=sys.stderr)
    raise SystemExit(1)

snapshot_date = sys.argv[1]
request = urllib.request.Request(
    f"http://127.0.0.1:8000/reports/daily/multi/wechat/article/generate?snapshot_date={snapshot_date}",
    method="POST",
    headers={"Authorization": f"Bearer {token}"},
)

try:
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
except urllib.error.HTTPError as exc:
    print(f"微信文章生成接口调用失败：HTTP {exc.code}", file=sys.stderr)
    raise SystemExit(1) from None
except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
    print(f"微信文章生成接口调用失败：{type(exc).__name__}", file=sys.stderr)
    raise SystemExit(1) from None

allowed = {"generated"}
if not isinstance(payload, dict) or payload.get("status") not in allowed:
    status = payload.get("status") if isinstance(payload, dict) else "invalid"
    print(f"微信文章生成接口调用失败：status={status}", file=sys.stderr)
    raise SystemExit(1)

print(
    "微信文章生成状态："
    f"{payload.get('status')}，新增岗位={payload.get('new_job_count')}，"
    f"基线就绪={payload.get('baseline_ready')}"
)
PY
}

create_wechat_draft() {
    local snapshot_date="$1"

    docker compose exec -T api python - "$snapshot_date" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

token = os.getenv("REPORT_TRIGGER_TOKEN")
if not token:
    print("微信草稿接口调用失败：缺少触发凭据", file=sys.stderr)
    raise SystemExit(1)

snapshot_date = sys.argv[1]
request = urllib.request.Request(
    f"http://127.0.0.1:8000/reports/daily/multi/wechat/draft/create?snapshot_date={snapshot_date}",
    method="POST",
    headers={"Authorization": f"Bearer {token}"},
)
try:
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
    print(f"微信草稿接口调用失败：{type(exc).__name__}", file=sys.stderr)
    raise SystemExit(1) from None

if not isinstance(payload, dict):
    print("微信草稿接口返回无效", file=sys.stderr)
    raise SystemExit(1)
print(f"微信草稿状态：{payload.get('status')}，已创建={payload.get('has_draft')}")
PY
}

merge_keyword_files() {
    local keyword_index="$1"
    local keyword_dir="$2"

    "$PYTHON" - "$keyword_dir" "$INBOX_DIR" "$keyword_index" <<'PY'
from pathlib import Path
import json
import os
import sys

keyword_dir = Path(sys.argv[1])
inbox_dir = Path(sys.argv[2])
keyword_index = sys.argv[3]

cities = ["上海", "北京", "杭州", "深圳"]
all_jobs = []
seen_job_ids = set()

for city in cities:
    path = keyword_dir / f"{city}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, list):
        jobs = data
    elif isinstance(data, dict) and isinstance(data.get("jobs"), list):
        jobs = data["jobs"]
    else:
        raise ValueError(f"{path} 的 JSON 结构不是岗位列表")

    if not jobs:
        raise ValueError(f"{city} 返回 0 条岗位，整批停止")

    print(f"{city}：{len(jobs)} 条")
    for job in jobs:
        job_id = str(job.get("job_id", "")).strip()
        if not job_id:
            raise ValueError(f"{city} 存在缺少 job_id 的岗位")
        if job_id not in seen_job_ids:
            seen_job_ids.add(job_id)
            all_jobs.append(job)

inbox_dir.mkdir(parents=True, exist_ok=True)

temporary_path = inbox_dir / f".jobflow-keyword-{keyword_index}.json.tmp"
final_path = inbox_dir / f"jobflow-keyword-{keyword_index}.json"

temporary_path.write_text(
    json.dumps({"jobs": all_jobs}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
os.replace(temporary_path, final_path)

print(f"合并完成：{len(all_jobs)} 条")
print(f"快照文件：{final_path}")
PY
}

capture_keyword() {
    local keyword="$1"
    local keyword_index="$2"
    local keyword_dir="$WORK_DIR/keyword-$keyword_index"

    mkdir -p "$keyword_dir"

    for city in "${CITIES[@]}"; do
        echo "开始抓取：$keyword / $city"
        "$PYTHON" "$SCRAPER_DIR/scripts/boss_cdp_raw.py" \
            --keyword "$keyword" \
            --city "$city" \
            --pages "$PAGES" \
            --no-detail \
            --format json \
            --output "$keyword_dir/${city}.json"
        echo "抓取完成：$keyword / $city"
    done

    merge_keyword_files "$keyword_index" "$keyword_dir"

    cd "$JOBFLOW_DIR"
    docker compose run --rm etl \
        "/data/raw/inbox/jobflow-keyword-${keyword_index}.json" \
        --snapshot-date "$SNAPSHOT_DATE" \
        --search-keyword "$keyword" \
        --cities "$(IFS=,; echo "${CITIES[*]}")" \
        --pages-per-city "$PAGES" \
        --detail-mode no-detail
}

echo "开始 JobFlow 多关键词每日更新"
echo "临时目录：$WORK_DIR"

cd "$JOBFLOW_DIR"

wait_for_api_ready

missing_indexes=()
for index in "${!KEYWORDS[@]}"; do
    keyword="${KEYWORDS[$index]}"
    if snapshot_exists "$SNAPSHOT_DATE" "$keyword"; then
        echo "$keyword 已存在快照，本关键词跳过抓取"
        continue
    else
        status=$?
    fi

    if [[ "$status" -ne 10 ]]; then
        echo "$keyword 快照状态不确定，本次停止"
        exit "$status"
    fi
    missing_indexes+=("$index")
done

if [[ "${#missing_indexes[@]}" -gt 0 ]]; then
    echo "开始检查 BOSS 抓取环境"
    if ! "$PYTHON" "$SCRAPER_DIR/scripts/boss_cdp_raw.py" --check; then
        echo "BOSS 抓取环境检查失败"
        echo "可能需要通过 VNC 重新登录，本次不更新缺失快照"
        exit 1
    fi
    echo "BOSS 抓取环境检查通过"

    for index in "${missing_indexes[@]}"; do
        keyword="${KEYWORDS[$index]}"
        capture_keyword "$keyword" "$index"
    done
else
    echo "四个关键词快照均已存在，跳过抓取"
fi

echo "并行发送 Telegram 图文简报并生成微信公告文章包"
send_multi_keyword_report "$SNAPSHOT_DATE" &
telegram_pid=$!
generate_wechat_article "$SNAPSHOT_DATE" &
wechat_article_pid=$!

set +e
wait "$telegram_pid"
telegram_status=$?
wait "$wechat_article_pid"
wechat_article_status=$?
set -e

if [[ "$wechat_article_status" -eq 0 ]]; then
    # 草稿是人工审核入口；失败只记录状态，不回滚文章包，也不影响 Telegram。
    if ! create_wechat_draft "$SNAPSHOT_DATE"; then
        echo "微信草稿创建失败，保留文章包并继续" >&2
    fi
fi

if [[ "$telegram_status" -ne 0 || "$wechat_article_status" -ne 0 ]]; then
    echo "渠道汇总失败：Telegram=$telegram_status，微信文章=$wechat_article_status" >&2
    exit 1
fi

echo "JobFlow 多关键词每日更新、Telegram 推送与微信文章生成完成"
