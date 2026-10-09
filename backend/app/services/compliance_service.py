"""合规校验服务。

校验维度：
- 禁用词（绝对化用语 / 医疗功效词 / 平台禁止的促销词）
- 字符限制（标题 ≤200、五点每点 ≤500、搜索词 ≤250 字节）
- 品牌侵权（是否含未授权品牌词）
- 类目特殊规则

规则来源：``app/data/compliance_rules/{MARKETPLACE}.json``，
并可叠加数据库中按 marketplace + category 存储的规则。
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.constants import LIMITS, language_for_marketplace
from app.core.logging import get_logger

logger = get_logger("app.compliance")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "compliance_rules"


class ComplianceService:
    def __init__(self, extra_rules: Optional[List[Dict[str, Any]]] = None) -> None:
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._extra_rules = extra_rules or []

    # ------------------------------------------------------------------ #
    # 规则加载
    # ------------------------------------------------------------------ #
    def load_rules(self, marketplace_id: str) -> Dict[str, Any]:
        """按站点加载规则（带内存缓存），叠加数据库规则。"""
        mid = (marketplace_id or "US").upper()
        if mid not in self._cache:
            path = DATA_DIR / f"{mid}.json"
            if path.exists():
                self._cache[mid] = json.loads(path.read_text(encoding="utf-8"))
            else:
                logger.warning("未找到站点规则，使用空规则", extra={"marketplace": mid})
                self._cache[mid] = {"marketplace_id": mid, "rules": [], "categories": {}}
        data = dict(self._cache[mid])
        if self._extra_rules:
            db_rules = [
                {"rule_type": r.get("rule_type", "banned_word"),
                 "description": r.get("description", ""),
                 "banned_words": r.get("banned_words", [])}
                for r in self._extra_rules
                if (r.get("marketplace_id") or "").upper() in (mid, "*")
                and r.get("category", "*") in ("*", "*")
            ]
            data["rules"] = list(data.get("rules", [])) + db_rules
        return data

    @staticmethod
    def _all_banned_words(rules: Dict[str, Any], category: str) -> List[Dict[str, str]]:
        """汇总通用 + 类目级禁用词，返回 [{type, word, description}]。"""
        collected: List[Dict[str, str]] = []
        for rule in rules.get("rules", []):
            for word in rule.get("banned_words", []):
                collected.append(
                    {
                        "type": rule.get("rule_type", "banned_word"),
                        "word": word,
                        "description": rule.get("description", ""),
                    }
                )
        cat = rules.get("categories", {}).get(category) or rules.get("categories", {}).get("*")
        if cat:
            for word in cat.get("banned_words", []):
                collected.append(
                    {"type": "category_rule", "word": word, "description": cat.get("note", "")}
                )
        return collected

    @staticmethod
    def _find_word(text: str, word: str) -> int:
        """返回命中位置（大小写不敏感），未命中返回 -1。"""
        if not text or not word:
            return -1
        match = re.search(re.escape(word), text, re.IGNORECASE)
        return match.start() if match else -1

    # ------------------------------------------------------------------ #
    # 校验入口
    # ------------------------------------------------------------------ #
    def validate(
        self,
        *,
        marketplace_id: str,
        category: str = "*",
        title: str = "",
        bullets: Optional[List[str]] = None,
        description: str = "",
        search_terms: str = "",
        brand_words: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        bullets = bullets or []
        brand_words = brand_words or []
        rules = self.load_rules(marketplace_id)
        banned = self._all_banned_words(rules, category)
        violations: List[Dict[str, Any]] = []

        fields = {"title": title, "description": description, "search_terms": search_terms}
        for idx, bullet in enumerate(bullets):
            fields[f"bullet[{idx}]"] = bullet

        # 1) 禁用词
        for item in banned:
            for field_name, value in fields.items():
                pos = self._find_word(value, item["word"])
                if pos >= 0:
                    violations.append(
                        {
                            "type": item["type"],
                            "word": item["word"],
                            "field": field_name,
                            "position": pos,
                            "message": f"命中{self._type_label(item['type'])}「{item['word']}」",
                            "suggestion": self._suggest_for_banned(item["word"]),
                        }
                    )

        # 2) 品牌侵权
        for brand in brand_words:
            for field_name, value in fields.items():
                pos = self._find_word(value, brand)
                if pos >= 0:
                    violations.append(
                        {
                            "type": "brand_infringement",
                            "word": brand,
                            "field": field_name,
                            "position": pos,
                            "message": f"疑似含未授权品牌词「{brand}」",
                            "suggestion": f"请移除品牌词「{brand}」或确认已获得授权",
                        }
                    )

        # 3) 字符限制
        violations.extend(self._check_limits(title, bullets, search_terms))

        passed = len(violations) == 0
        return {"passed": passed, "violations": violations}

    def _check_limits(
        self, title: str, bullets: List[str], search_terms: str
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if title and len(title) > LIMITS["title"]:
            out.append(
                {
                    "type": "char_limit",
                    "word": "",
                    "field": "title",
                    "position": LIMITS["title"],
                    "message": f"标题长度 {len(title)} 超过限制 {LIMITS['title']} 字符",
                    "suggestion": "建议调用 LLM 压缩改写而非直接截断，保留核心关键词",
                }
            )
        for idx, bullet in enumerate(bullets):
            if len(bullet) > LIMITS["bullet"]:
                out.append(
                    {
                        "type": "char_limit",
                        "word": "",
                        "field": f"bullet[{idx}]",
                        "position": LIMITS["bullet"],
                        "message": f"第 {idx + 1} 点长度 {len(bullet)} 超过限制 {LIMITS['bullet']} 字符",
                        "suggestion": "建议调用 LLM 压缩改写而非直接截断，保留核心利益点",
                    }
                )
        if search_terms:
            size = len(search_terms.encode("utf-8"))
            if size > LIMITS["search_terms"]:
                out.append(
                    {
                        "type": "char_limit",
                        "word": "",
                        "field": "search_terms",
                        "position": LIMITS["search_terms"],
                        "message": f"搜索词 {size} 字节超过限制 {LIMITS['search_terms']} 字节",
                        "suggestion": "建议删除低相关关键词，优先保留核心长尾词",
                    }
                )
        return out

    @staticmethod
    def _type_label(rule_type: str) -> str:
        return {
            "absolute_term": "绝对化用语",
            "medical_claim": "医疗功效词",
            "promo_term": "促销诱导词",
            "category_rule": "类目特殊规则",
            "brand_infringement": "品牌侵权词",
            "char_limit": "字符超限",
        }.get(rule_type, "违禁词")

    @staticmethod
    def _suggest_for_banned(word: str) -> str:
        return f"删除或替换「{word}」，改用客观、可核实的描述（如具体规格或参数）"

    def target_language(self, marketplace_id: str) -> str:
        return language_for_marketplace(marketplace_id)
