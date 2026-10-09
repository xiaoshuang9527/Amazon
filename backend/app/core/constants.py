"""业务常量：站点与语言映射、字符限制等。"""

from typing import Dict

# 站点 → 目标语言
MARKETPLACE_LANGUAGE: Dict[str, str] = {
    "US": "en",
    "CA": "en",
    "UK": "en",
    "GB": "en",
    "DE": "de",
    "FR": "fr",
    "IT": "it",
    "ES": "es",
    "JP": "ja",
    "MX": "es",
    "AU": "en",
}

MARKETPLACE_LABEL: Dict[str, str] = {
    "US": "美国站",
    "CA": "加拿大站",
    "UK": "英国站",
    "GB": "英国站",
    "DE": "德国站",
    "FR": "法国站",
    "IT": "意大利站",
    "ES": "西班牙站",
    "JP": "日本站",
    "MX": "墨西哥站",
    "AU": "澳大利亚站",
}

LANGUAGE_LABEL: Dict[str, str] = {
    "en": "英语",
    "de": "德语",
    "fr": "法语",
    "it": "意大利语",
    "es": "西班牙语",
    "ja": "日语",
    "zh": "中文",
}

# 字符 / 字节限制
LIMITS = {
    "title": 200,          # 字符
    "bullet": 500,         # 字符（每条）
    "search_terms": 250,   # 字节
}


def language_for_marketplace(marketplace_id: str) -> str:
    """站点 → 语言；未知站点回退英语。"""
    return MARKETPLACE_LANGUAGE.get((marketplace_id or "").upper(), "en")


SUPPORTED_MARKETPLACES = sorted(set(MARKETPLACE_LANGUAGE.keys()))
