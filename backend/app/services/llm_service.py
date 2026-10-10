"""LLM 统一网关。

- 抽象基类 ``LLMProvider``，提供 ``generate(messages, **kwargs)``；
- 具体实现 ``DeepSeekProvider`` / ``OpenAIProvider``（均走 OpenAI 兼容协议）；
- ``LLMGateway`` 负责按任务类型路由模型、自动重试、令牌桶限流、
  记录 token 消耗与成本、Prompt 缓存标记。

所有 LLM 调用必须经过本网关，禁止在业务代码中直接发起 HTTP 请求。
"""

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.constants import language_for_marketplace
from app.core.exceptions import UpstreamError
from app.core.logging import get_logger
from app.core.rate_limit import TokenBucket, retry_async

logger = get_logger("app.llm")

# 每 1K token 的价格（USD），用于成本估算；可按需在配置中覆盖
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "deepseek-chat": {"input": 0.00027, "output": 0.0011},
    "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}

# 网关级令牌桶：限制对外部 LLM 的并发/速率
_LLM_BUCKET = TokenBucket(
    capacity=settings.RATE_LIMIT_CAPACITY,
    refill_per_sec=settings.RATE_LIMIT_REFILL_PER_SEC,
)


@dataclass
class LLMResponse:
    """一次 LLM 调用的返回。"""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> Dict[str, Any]:
        """把 content 解析为 JSON 字典（容错处理 Markdown 代码块）。"""
        return parse_json_content(self.content)


def parse_json_content(content: str) -> Dict[str, Any]:
    """从模型输出中稳健地提取 JSON 对象。"""
    if not content:
        return {}
    text = content.strip()
    # 去除 ```json ... ``` 包裹
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    logger.warning("LLM 输出无法解析为 JSON", extra={"preview": text[:200]})
    return {}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price = MODEL_PRICING.get(model)
    if not price:
        return 0.0
    return round(
        input_tokens / 1000 * price["input"] + output_tokens / 1000 * price["output"], 6
    )


# --------------------------------------------------------------------------- #
# Provider
# --------------------------------------------------------------------------- #
class LLMProvider(ABC):
    """LLM 提供方抽象基类。"""

    name: str = "base"

    def __init__(self, api_key: str, base_url: str, timeout: float = 60.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @abstractmethod
    async def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        """根据 messages 生成回复。"""
        raise NotImplementedError

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()


class DeepSeekProvider(LLMProvider):
    """DeepSeek（OpenAI 兼容协议）。"""

    name = "deepseek"

    async def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        model = kwargs.get("model") or settings.LLM_MODEL_STANDARD
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "response_format": {"type": "json_object"},
        }
        data = await self._post_chat(payload)
        return _build_response(data, model)


class OpenAIProvider(LLMProvider):
    """OpenAI（OpenAI 兼容协议）。"""

    name = "openai"

    async def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        model = kwargs.get("model") or "gpt-4o-mini"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "response_format": {"type": "json_object"},
        }
        data = await self._post_chat(payload)
        return _build_response(data, model)


class AgnesProvider(LLMProvider):
    """Agnes AI（OpenAI 兼容协议，聚合网关）。

    与官方 OpenAI 的两点差异，这里做兼容处理：
    1. 只接受字符串形式的 message content，不认 Anthropic 风格的
       content 数组（含 cache_control），因此发送前先压平；
    2. 未必支持 ``response_format={"type": "json_object"}``，先试带该参数，
       若被拒（4xx）则去掉重试一次。
    """

    name = "agnes"

    @staticmethod
    def _flatten_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flattened: List[Dict[str, Any]] = []
        for message in messages:
            content = message.get("content")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        parts.append(str(item.get("text", "")))
                    else:
                        parts.append(str(item))
                content = "\n".join(p for p in parts if p)
            flattened.append({"role": message.get("role", "user"), "content": content})
        return flattened

    async def generate(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        model = kwargs.get("model") or settings.LLM_MODEL_STANDARD
        payload = {
            "model": model,
            "messages": self._flatten_messages(messages),
            "temperature": kwargs.get("temperature", 0.7),
        }
        try:
            data = await self._post_chat({**payload, "response_format": {"type": "json_object"}})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 404, 422):
                logger.warning(
                    "Agnes 拒绝 response_format，降级为普通模式重试",
                    extra={"status": exc.response.status_code},
                )
                data = await self._post_chat(payload)
            else:
                raise
        return _build_response(data, model)


def _build_response(data: Dict[str, Any], model: str) -> LLMResponse:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise UpstreamError("LLM 返回结构异常", details=data) from exc
    usage = data.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens", 0))
    output_tokens = int(usage.get("completion_tokens", 0))
    return LLMResponse(
        content=content,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=estimate_cost(model, input_tokens, output_tokens),
        raw=data,
    )


# --------------------------------------------------------------------------- #
# Gateway
# --------------------------------------------------------------------------- #
class LLMGateway:
    """统一网关：模型路由 + 重试 + 限流 + Prompt 模板渲染。"""

    def __init__(self, provider: Optional[LLMProvider] = None) -> None:
        self.provider = provider or self._build_provider()
        self.prompts = PromptRenderer()

    @staticmethod
    def _build_provider() -> LLMProvider:
        if settings.LLM_PROVIDER == "agnes":
            return AgnesProvider(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL,
                timeout=settings.LLM_TIMEOUT,
            )
        if settings.LLM_PROVIDER == "openai":
            return OpenAIProvider(
                api_key=settings.LLM_API_KEY,
                base_url=settings.LLM_BASE_URL or "https://api.openai.com/v1",
                timeout=settings.LLM_TIMEOUT,
            )
        return DeepSeekProvider(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT,
        )

    def model_for_quality(self, quality: str) -> str:
        """按质量模式选择模型：高质量用 Pro/大模型，标准用 Flash/小模型。"""
        if quality == "high":
            return settings.LLM_MODEL_HIGH
        return settings.LLM_MODEL_STANDARD

    def build_messages(
        self, template_name: str, variables: Dict[str, Any], quality: str = "standard"
    ) -> List[Dict[str, Any]]:
        """渲染 Jinja2 模板，构造 messages。系统提示词标记 cache_control 以命中缓存。"""
        user_prompt = self.prompts.render(template_name, variables)
        system = {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "你是亚马逊 Listing 本地化文案专家，严格按 JSON 格式输出。",
                    # 固定系统提示词标记缓存，降低重复成本
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
        return [system, {"role": "user", "content": user_prompt}]

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        *,
        quality: str = "standard",
        model: Optional[str] = None,
    ) -> LLMResponse:
        """调用底层 provider，带限流与指数退避重试。"""
        chosen_model = model or self.model_for_quality(quality)

        async def _call() -> LLMResponse:
            return await self.provider.generate(messages, model=chosen_model)

        return await retry_async(
            _call,
            max_retries=settings.LLM_MAX_RETRIES,
            base_delay=settings.RETRY_BASE_DELAY,
            max_delay=settings.RETRY_MAX_DELAY,
            bucket=_LLM_BUCKET,
        )

    async def generate_json(
        self,
        template_name: str,
        variables: Dict[str, Any],
        *,
        quality: str = "standard",
    ) -> LLMResponse:
        """渲染模板 → 调用模型 → 返回带解析能力的结果。"""
        messages = self.build_messages(template_name, variables, quality=quality)
        return await self.complete(messages, quality=quality)


class PromptRenderer:
    """Jinja2 模板渲染器，从 app/prompts/ 目录加载模板。"""

    def __init__(self) -> None:
        from pathlib import Path

        from jinja2 import Environment, FileSystemLoader, StrictUndefined

        self._dir = Path(__file__).resolve().parent.parent / "prompts"
        self.env = Environment(
            loader=FileSystemLoader(str(self._dir)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, variables: Dict[str, Any]) -> str:
        template = self.env.get_template(template_name)
        return template.render(**variables)

    def build_variables(
        self,
        *,
        product_info: Dict[str, Any],
        target_marketplace: str,
        target_language: Optional[str] = None,
        category: str = "*",
        keywords: Optional[List[str]] = None,
        tone: str = "professional",
    ) -> Dict[str, Any]:
        lang = target_language or language_for_marketplace(target_marketplace)
        return {
            "product_info": json.dumps(product_info, ensure_ascii=False, indent=2),
            "target_marketplace": target_marketplace,
            "target_language": lang,
            "category": category,
            "keywords": ", ".join(keywords or []) or "无",
            "tone": tone,
        }


_gateway_singleton: Optional[LLMGateway] = None


def get_llm_gateway() -> LLMGateway:
    """返回网关单例（便于测试时替换）。"""
    global _gateway_singleton
    if _gateway_singleton is None:
        _gateway_singleton = LLMGateway()
    return _gateway_singleton
