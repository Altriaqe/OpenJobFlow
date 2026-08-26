"""通用 HTTP 采集边界，将 requests 异常转换为项目异常。"""

import requests


class FetchError(Exception):
    """JobFlow 数据采集失败。"""


def fetch_json(url: str) -> dict[str, object]:
    """从 URL 获取 JSON；网络、HTTP 和解析错误统一转换为 ``FetchError``。"""

    try:
        response = requests.get(url, timeout=10)
    except requests.Timeout as exc:
        raise FetchError(f"请求 {url} 超时") from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise FetchError(f"请求 {url} 返回 HTTP 错误") from exc

    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise FetchError(f"请求 {url} 返回无效的 JSON") from exc
