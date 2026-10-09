"""LLM 网关测试：JSON 解析、成本估算、模型路由、Prompt 模板渲染、重试。"""

import asyncio

import pytest

from app.core.config import settings
from app.core.exceptions import UpstreamError
from app.services.llm_service import (
    MODEL_PRICING,
    DeepSeekProvider,
    LLMGateway,
    LLMProvider,
    LLMResponse,
    OpenAIProvider,
    PromptRenderer,
    _build_response,
    estimate_cost,
    get_llm_gateway,
    parse_json_content,
)


# --------------------------------------------------------------------------- #
# JSON 解析
# --------------------------------------------------------------------------- #
def test_parse_json_content_plain_object():
    assert parse_json_content('{"title": "hello"}') == {"title": "hello"}


def test_parse_json_content_fenced_block():
    raw = '```json\n{"bullets": ["a", "b"]}\n```'
    assert parse_json_content(raw) == {"bullets": ["a", "b"]}


def test_parse_json_content_with_surrounding_prose():
    raw = 'Here is the result:\n{"search_terms": "abc"}\nHope it helps.'
    assert parse_json_content(raw) == {"search_terms": "abc"}


@pytest.mark.parametrize("raw", ["", "   ", "no json at all", "{broken json"])
def test_parse_json_content_returns_empty_on_failure(raw):
    assert parse_json_content(raw) == {}


def test_llm_response_as_json():
    resp = LLMResponse(content='{"title": "t"}', model="m")
    assert resp.as_json() == {"title": "t"}


# --------------------------------------------------------------------------- #
# 成本估算
# --------------------------------------------------------------------------- #
def test_estimate_cost_known_model():
    expected = 1000 / 1000 * MODEL_PRICING["deepseek-chat"]["input"] + 1000 / 1000 * MODEL_PRICING[
        "deepseek-chat"
    ]["output"]
    assert estimate_cost("deepseek-chat", 1000, 1000) == pytest.approx(expected)


def test_estimate_cost_unknown_model_is_zero():
    assert estimate_cost("unknown-model", 1000, 1000) == 0.0


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
def test_build_response_extracts_usage():
    payload = {
        "choices": [{"message": {"content": '{"title": "x"}'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    resp = _build_response(payload, "deepseek-chat")
    assert resp.content == '{"title": "x"}'
    assert (resp.input_tokens, resp.output_tokens) == (100, 50)
    assert resp.cost_usd > 0


def test_build_response_raises_on_malformed_payload():
    with pytest.raises(UpstreamError):
        _build_response({"unexpected": True}, "deepseek-chat")


def test_provider_generate_with_mocked_transport(monkeypatch):
    provider = DeepSeekProvider(api_key="k", base_url="https://example.invalid/v1")
    captured = {}

    async def _fake_post(payload):
        captured.update(payload)
        return {
            "choices": [{"message": {"content": '{"title": "ok"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    monkeypatch.setattr(provider, "_post_chat", _fake_post)
    resp = asyncio.run(provider.generate([{"role": "user", "content": "hi"}], model="deepseek-chat"))

    assert resp.model == "deepseek-chat"
    assert captured["model"] == "deepseek-chat"
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages"][0]["content"] == "hi"


# --------------------------------------------------------------------------- #
# 网关路由
# --------------------------------------------------------------------------- #
def test_gateway_builds_deepseek_provider_by_default():
    assert LLMGateway().provider.name == "deepseek"


def test_gateway_builds_openai_provider_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    assert LLMGateway().provider.name == "openai"


def test_model_for_quality_routing():
    gateway = LLMGateway()
    assert gateway.model_for_quality("standard") == settings.LLM_MODEL_STANDARD
    assert gateway.model_for_quality("high") == settings.LLM_MODEL_HIGH


def test_build_messages_marks_system_prompt_for_cache():
    gateway = LLMGateway()
    messages = gateway.build_messages(
        "listing_title.j2",
        gateway.prompts.build_variables(
            product_info={"title": "测试产品"}, target_marketplace="US"
        ),
    )
    assert messages[0]["role"] == "system"
    assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert messages[1]["role"] == "user"
    assert "US" in messages[1]["content"]


class _RetryingProvider(LLMProvider):
    name = "stub"

    def __init__(self, fail_times: int = 1) -> None:
        super().__init__(api_key="k", base_url="https://example.invalid/v1")
        self.fail_times = fail_times
        self.calls = 0

    async def generate(self, messages, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient")
        return LLMResponse(content='{"title": "ok"}', model=kwargs.get("model", "stub"))


def test_gateway_complete_retries_transient_failures(monkeypatch):
    monkeypatch.setattr(settings, "RETRY_BASE_DELAY", 0.001)
    monkeypatch.setattr(settings, "RETRY_MAX_DELAY", 0.002)
    provider = _RetryingProvider(fail_times=1)
    gateway = LLMGateway(provider=provider)

    resp = asyncio.run(gateway.complete([{"role": "user", "content": "hi"}]))
    assert resp.content == '{"title": "ok"}'
    assert provider.calls == 2


def test_gateway_complete_raises_after_retries_exhausted(monkeypatch):
    monkeypatch.setattr(settings, "RETRY_BASE_DELAY", 0.001)
    monkeypatch.setattr(settings, "RETRY_MAX_DELAY", 0.002)
    monkeypatch.setattr(settings, "LLM_MAX_RETRIES", 1)
    provider = _RetryingProvider(fail_times=99)
    gateway = LLMGateway(provider=provider)

    with pytest.raises(UpstreamError):
        asyncio.run(gateway.complete([{"role": "user", "content": "hi"}]))
    assert provider.calls == 2


def test_generate_json_renders_template_and_calls_provider(monkeypatch):
    provider = _RetryingProvider(fail_times=0)
    gateway = LLMGateway(provider=provider)
    variables = gateway.prompts.build_variables(
        product_info={"title": "耳机"}, target_marketplace="DE"
    )
    resp = asyncio.run(gateway.generate_json("listing_title.j2", variables, quality="high"))
    assert resp.as_json() == {"title": "ok"}


def test_get_llm_gateway_returns_singleton():
    assert get_llm_gateway() is get_llm_gateway()


# --------------------------------------------------------------------------- #
# Prompt 模板
# --------------------------------------------------------------------------- #
@pytest.fixture()
def renderer() -> PromptRenderer:
    return PromptRenderer()


def test_prompt_templates_all_render(renderer):
    variables = renderer.build_variables(
        product_info={"title": "无线蓝牙耳机", "bullets": ["续航 40 小时"]},
        target_marketplace="US",
        category="Electronics",
        keywords=["wireless headphones"],
        tone="professional",
    )
    for template in (
        "listing_title.j2",
        "listing_bullets.j2",
        "listing_description.j2",
        "listing_search_terms.j2",
        "keyword_suggest.j2",
    ):
        rendered = renderer.render(template, variables)
        assert isinstance(rendered, str) and len(rendered) > 20
        assert "US" in rendered and "en" in rendered


def test_prompt_variables_include_product_info_and_keywords(renderer):
    variables = renderer.build_variables(
        product_info={"title": "产品 A"},
        target_marketplace="JP",
        keywords=["キーワード"],
        tone="friendly",
    )
    assert variables["target_language"] == "ja"
    assert "キーワード" in variables["keywords"]
    assert variables["category"] == "*"
    assert "产品 A" in variables["product_info"]
    assert variables["tone"] == "friendly"


def test_prompt_render_fails_on_missing_variable(renderer):
    with pytest.raises(Exception):
        renderer.render("listing_title.j2", {"target_marketplace": "US"})
