"""微信测试号模板字段构建器：把文章聚合数据转换为受限文本字段。"""

from jobflow.reports.wechat_article import WechatArticleData


FIELD_LIMIT = 80


def _clean(value: object, *, limit: int = FIELD_LIMIT) -> str:
    """压缩换行和连续空白，并限制单个模板字段长度。"""
    normalized = " ".join(str(value).split())
    return normalized[:limit]


def build_wechat_template_data(data: WechatArticleData) -> dict[str, dict[str, str]]:
    """生成与 `JobFlow日报` 测试模板一致的微信 data 字段。"""
    if not data.keyword_rows:
        raise ValueError("template requires keyword rows")
    total_jobs = sum(total for _keyword, total, _new_count in data.keyword_rows)
    new_values = [new_count for _keyword, _total, new_count in data.keyword_rows]
    new_jobs = "基线建立中" if any(value is None for value in new_values) else str(sum(new_values))
    top_keyword, top_total, _new_count = min(
        data.keyword_rows,
        key=lambda row: (-row[1], row[0]),
    )
    if data.city_advantages:
        top_city, city_keyword, city_count = min(
            data.city_advantages,
            key=lambda row: (-row[2], row[1], row[0]),
        )
        top_city_value = f"{city_keyword} / {top_city}（{city_count}）"
    else:
        top_city_value = "基线建立中"
    remark = (
        f"固定范围样本：{data.city_count} 城市 × 每城 {data.pages_per_city} 页，"
        "仅供学习研究，不代表全市场总量"
    )
    values = {
        "first": "JobFlow 多关键词日报已生成",
        "report_date": data.report_date.isoformat(),
        "total_jobs": total_jobs,
        "new_jobs": new_jobs,
        "top_keyword": f"{top_keyword}（{top_total}）",
        "top_city": top_city_value,
        "remark": remark,
    }
    return {name: {"value": _clean(value)} for name, value in values.items()}
