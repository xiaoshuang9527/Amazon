"""pytest 公共夹具。

- 测试使用独立的 SQLite 文件库，避免依赖 PostgreSQL；
- LLM 与 SP-API 一律用假实现替换，测试绝不发起真实网络请求。
"""

import json
import os
import pathlib
import sys
import tempfile

# --------------------------------------------------------------------------- #
# 必须在导入 app 之前设置环境变量（Settings 在 import 时实例化）
# --------------------------------------------------------------------------- #
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_TMP_DIR = pathlib.Path(tempfile.mkdtemp(prefix="listing-mvp-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["LOG_DIR"] = str(_TMP_DIR / "logs")
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["SQL_ECHO"] = "false"
os.environ["JWT_SECRET"] = "unit-test-secret"
os.environ["LLM_API_KEY"] = "unit-test-key"
os.environ["LLM_PROVIDER"] = "deepseek"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: E402,F401  （注册所有 ORM 映射）
from app.api.deps import get_session as deps_get_session  # noqa: E402
from app.core.db import SessionLocal, engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.services.llm_service import LLMResponse  # noqa: E402

# --------------------------------------------------------------------------- #
# 假 LLM 网关
# --------------------------------------------------------------------------- #
TEMPLATE_PAYLOADS = {
    "listing_title.j2": {
        "title": "Wireless Bluetooth Headphones, Over-Ear Design, 40H Playtime for Travel and Work"
    },
    "listing_bullets.j2": {
        "bullets": [
            "40 hours of playtime keeps your music going through long trips",
            "Over-ear cushion design stays comfortable during extended wear",
            "Bluetooth 5.3 connection pairs quickly with phones and laptops",
            "Foldable frame fits easily into a backpack or carry-on bag",
            "Built-in microphone supports clear hands-free calls at home or in the office",
        ]
    },
    "listing_description.j2": {
        "description": (
            "These over-ear wireless headphones are built for daily commuting, "
            "remote work and travel. The 40-hour battery keeps playback going "
            "without frequent charging, while the cushioned earcups reduce "
            "pressure during long listening sessions."
        )
    },
    "listing_search_terms.j2": {
        "search_terms": "wireless headphones bluetooth over ear travel office"
    },
    "keyword_suggest.j2": {
        "suggested_keywords": ["wireless headphones", "over ear bluetooth", "travel headphones"]
    },
}


class FakeLLMGateway:
    """测试用网关：按模板返回预置 JSON，记录调用轨迹。"""

    def __init__(self, model: str = "fake-model", payloads=None) -> None:
        self.model = model
        self.calls = []
        self._payloads = payloads or TEMPLATE_PAYLOADS

    async def generate_json(self, template_name, variables, *, quality="standard"):
        self.calls.append({"template": template_name, "quality": quality, "variables": variables})
        payload = self._payloads.get(template_name, {})
        return LLMResponse(
            content=json.dumps(payload, ensure_ascii=False),
            model=self.model,
            input_tokens=120,
            output_tokens=80,
            cost_usd=0.0002,
        )


VIOLATING_PAYLOADS = dict(TEMPLATE_PAYLOADS)
VIOLATING_PAYLOADS["listing_title.j2"] = {
    "title": "Best Wireless Headphones, Cheapest Price with Free Shipping for Travel"
}


class SequencedLLMGateway(FakeLLMGateway):
    """前 N 次返回违规文案，之后返回合规文案（用于测试自动重写）。"""

    def __init__(self, violating_rounds: int = 1, **kwargs) -> None:
        super().__init__(**kwargs)
        self.violating_rounds = violating_rounds
        self.title_calls = 0

    async def generate_json(self, template_name, variables, *, quality="standard"):
        if template_name == "listing_title.j2":
            self.title_calls += 1
            payloads = VIOLATING_PAYLOADS if self.title_calls <= self.violating_rounds else TEMPLATE_PAYLOADS
            self.calls.append({"template": template_name, "quality": quality, "variables": variables})
            return LLMResponse(
                content=json.dumps(payloads[template_name], ensure_ascii=False),
                model=self.model,
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.0001,
            )
        return await super().generate_json(template_name, variables, quality=quality)


# --------------------------------------------------------------------------- #
# 建表 / 清理
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """每个用例结束后清空所有表，保证用例之间互不污染。"""
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture()
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> TestClient:
    """TestClient，并把数据库依赖指向测试库。"""

    def _override():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps_get_session] = _override
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def fake_gateway() -> FakeLLMGateway:
    return FakeLLMGateway()


@pytest.fixture()
def patched_gateway(monkeypatch, fake_gateway):
    """把生成链路上的 LLM 网关替换为假实现。"""
    import app.services.generation_service as generation_service
    import app.services.llm_service as llm_service

    monkeypatch.setattr(generation_service, "get_llm_gateway", lambda: fake_gateway)
    monkeypatch.setattr(llm_service, "_gateway_singleton", fake_gateway)
    return fake_gateway


@pytest.fixture()
def user_token(client: TestClient) -> str:
    """注册并登录一个测试用户，返回访问令牌。"""
    client.post(
        "/api/v1/auth/register",
        json={"email": "tester@example.com", "password": "secret123"},
    )
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "tester@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}"}


SAMPLE_SOURCE_CONTENT = {
    "title": "无线蓝牙耳机 头戴式 40小时续航 折叠便携",
    "bullets": [
        "40 小时续航，长途旅行不断电",
        "头戴式蛋白皮耳罩，久戴不压迫",
        "蓝牙 5.3 快速配对手机与电脑",
        "可折叠设计，方便收纳进背包",
        "内置麦克风，支持免提通话",
    ],
    "description": "适合通勤、远程办公与旅行的头戴式无线耳机，40 小时续航减少充电次数。",
    "keywords": ["无线耳机", "蓝牙耳机", "头戴式耳机"],
    "attributes": {"battery": "40H", "connectivity": "Bluetooth 5.3"},
}
