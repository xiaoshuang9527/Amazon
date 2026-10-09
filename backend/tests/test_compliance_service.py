"""合规校验服务测试：禁用词 / 字符限制 / 品牌词 / 类目规则 / 多站点规则。"""

import pytest

from app.services.compliance_service import ComplianceService

CLEAN_TITLE = "Wireless Bluetooth Headphones, Over-Ear Design, 40H Playtime for Travel and Work"
CLEAN_BULLETS = [
    "40 hours of playtime keeps your music going through long trips",
    "Over-ear cushion design stays comfortable during extended wear",
]
CLEAN_DESCRIPTION = "Built for commuting, remote work and travel with a 40-hour battery."
CLEAN_SEARCH_TERMS = "wireless headphones bluetooth over ear travel office"


@pytest.fixture()
def service() -> ComplianceService:
    return ComplianceService()


def _types(report) -> set:
    return {v["type"] for v in report["violations"]}


# --------------------------------------------------------------------------- #
# 正常文案
# --------------------------------------------------------------------------- #
def test_clean_copy_passes(service):
    report = service.validate(
        marketplace_id="US",
        category="Electronics",
        title=CLEAN_TITLE,
        bullets=CLEAN_BULLETS,
        description=CLEAN_DESCRIPTION,
        search_terms=CLEAN_SEARCH_TERMS,
    )
    assert report["passed"] is True
    assert report["violations"] == []


def test_clean_copy_passes_on_de_and_jp(service):
    for marketplace in ("DE", "JP"):
        report = service.validate(
            marketplace_id=marketplace,
            title=CLEAN_TITLE,
            bullets=CLEAN_BULLETS,
            description=CLEAN_DESCRIPTION,
            search_terms=CLEAN_SEARCH_TERMS,
        )
        assert report["passed"] is True, marketplace


# --------------------------------------------------------------------------- #
# 禁用词
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "text,expected_word",
    [
        ("Best Wireless Headphones for Travel", "best"),
        ("Cheapest Price Bluetooth Speaker", "cheapest"),
        ("Free Shipping Wireless Mouse", "free shipping"),
        ("This device cures headaches quickly", "cures"),
    ],
)
def test_banned_words_are_detected(service, text, expected_word):
    report = service.validate(marketplace_id="US", title=text)
    assert report["passed"] is False
    hit = [v for v in report["violations"] if v["word"].lower() == expected_word]
    assert hit, report["violations"]
    assert hit[0]["field"] == "title"
    assert hit[0]["position"] >= 0
    assert hit[0]["suggestion"]


def test_banned_word_detection_is_case_insensitive(service):
    report = service.validate(marketplace_id="US", title="BEST quality headphones")
    assert any(v["word"] == "best" for v in report["violations"])


def test_banned_word_in_bullet_reports_field_index(service):
    report = service.validate(
        marketplace_id="US",
        bullets=["Great sound", "Guaranteed satisfaction for every buyer"],
    )
    fields = {v["field"] for v in report["violations"]}
    assert "bullet[1]" in fields
    assert any(v["word"] == "guaranteed" for v in report["violations"])


def test_banned_word_in_description_and_search_terms(service):
    report = service.validate(
        marketplace_id="US",
        description="Perfect for every home gym",
        search_terms="unbeatable speaker deals",
    )
    fields = {v["field"] for v in report["violations"]}
    assert "description" in fields and "search_terms" in fields


def test_jp_and_de_banned_words(service):
    jp = service.validate(marketplace_id="JP", title="最高品質のワイヤレスヘッドホン")
    assert "最高" in {v["word"] for v in jp["violations"]}

    jp_promo = service.validate(marketplace_id="JP", title="今すぐ買う ヘッドホン 送料無料")
    assert {"今すぐ買う", "送料無料"} <= {v["word"] for v in jp_promo["violations"]}

    de = service.validate(marketplace_id="DE", title="beste Qualität Kopfhörer")
    assert "beste" in {v["word"] for v in de["violations"]}


# --------------------------------------------------------------------------- #
# 字符限制
# --------------------------------------------------------------------------- #
def test_title_length_limit(service):
    report = service.validate(marketplace_id="US", title="A" * 201)
    limits = [v for v in report["violations"] if v["type"] == "char_limit"]
    assert limits and limits[0]["field"] == "title"
    assert "200" in limits[0]["message"]


def test_bullet_length_limit(service):
    report = service.validate(marketplace_id="US", bullets=["A" * 501])
    limits = [v for v in report["violations"] if v["type"] == "char_limit"]
    assert limits and limits[0]["field"] == "bullet[0]"


def test_search_terms_byte_limit(service):
    # 每个中文字符 3 字节，90 个字符 = 270 字节 > 250
    report = service.validate(marketplace_id="US", search_terms="耳" * 90)
    limits = [v for v in report["violations"] if v["type"] == "char_limit"]
    assert limits and limits[0]["field"] == "search_terms"
    assert "字节" in limits[0]["message"]


def test_length_within_limit_passes(service):
    report = service.validate(
        marketplace_id="US", title="A" * 200, bullets=["B" * 500], search_terms="c" * 250
    )
    assert report["passed"] is True


# --------------------------------------------------------------------------- #
# 品牌词
# --------------------------------------------------------------------------- #
def test_brand_word_detection(service):
    report = service.validate(
        marketplace_id="US",
        title="Nike Style Sports Armband",
        brand_words=["Nike", "Adidas"],
    )
    assert report["passed"] is False
    brands = [v for v in report["violations"] if v["type"] == "brand_infringement"]
    assert [b["word"] for b in brands] == ["Nike"]
    assert "授权" in brands[0]["suggestion"]


def test_no_brand_words_means_no_brand_violation(service):
    report = service.validate(marketplace_id="US", title="Sports Armband for Phone")
    assert "brand_infringement" not in _types(report)


# --------------------------------------------------------------------------- #
# 类目规则
# --------------------------------------------------------------------------- #
def test_category_specific_rule(service):
    report = service.validate(
        marketplace_id="US", category="Electronics", title="Unbreakable wireless charger"
    )
    assert "category_rule" in _types(report)


def test_category_rule_not_applied_for_other_category(service):
    report = service.validate(
        marketplace_id="US", category="Sports", title="Unbreakable water bottle"
    )
    assert report["passed"] is True


# --------------------------------------------------------------------------- #
# 规则加载
# --------------------------------------------------------------------------- #
def test_unknown_marketplace_falls_back_to_empty_rules(service):
    report = service.validate(marketplace_id="XX", title="Best Free Shipping Deal")
    assert report["passed"] is True


def test_extra_db_rules_are_merged(service):
    extra = [
        {
            "marketplace_id": "US",
            "category": "*",
            "rule_type": "banned_word",
            "description": "自定义规则",
            "banned_words": ["superx"],
        }
    ]
    svc = ComplianceService(extra_rules=extra)
    report = svc.validate(marketplace_id="US", title="superx wireless charger")
    assert any(v["word"] == "superx" for v in report["violations"])


def test_rules_are_cached_per_marketplace(service):
    first = service.load_rules("US")
    second = service.load_rules("us")  # 大小写不敏感且命中缓存
    assert first["marketplace_id"] == second["marketplace_id"] == "US"


@pytest.mark.parametrize(
    "marketplace,expected",
    [("US", "en"), ("DE", "de"), ("JP", "ja"), ("FR", "fr"), ("UNKNOWN", "en")],
)
def test_target_language_mapping(service, marketplace, expected):
    assert service.target_language(marketplace) == expected
