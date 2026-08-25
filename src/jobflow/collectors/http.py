import requests


class FetchError(Exception):
    """JobFlow 数据采集失败。"""


def fetch_json(url: str) -> dict[str, object]:
    """实现从给定的 URL 获取 JSON 数据的函数。"""

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
