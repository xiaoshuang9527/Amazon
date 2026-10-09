---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 727a7970f4b7df79363f5322a4753fc9_f90f4152c38611f18019525400248c00
    ReservedCode1: qktvfEHgL6a6JyQipGk5Eo6NWZk2rp4n+/E6eJfzEjn+mAQCR+BA3KG4BHor9JDVBwypHS1urrMBOT6uezsqjZfH4FnufocEP0hp6qogjl/yA2IyqzhFH7/mtNDMq4m7IcXlg7aYUPmI/t7sbGbytX9J5p6y9zo9gYTk1xY1PdtjLzZ1P1tYsCop91E=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 727a7970f4b7df79363f5322a4753fc9_f90f4152c38611f18019525400248c00
    ReservedCode2: qktvfEHgL6a6JyQipGk5Eo6NWZk2rp4n+/E6eJfzEjn+mAQCR+BA3KG4BHor9JDVBwypHS1urrMBOT6uezsqjZfH4FnufocEP0hp6qogjl/yA2IyqzhFH7/mtNDMq4m7IcXlg7aYUPmI/t7sbGbytX9J5p6y9zo9gYTk1xY1PdtjLzZ1P1tYsCop91E=
---

# 亚马逊 Listing 多语言文案生成工具（MVP）

面向中国亚马逊多站点卖家的 AI Listing 本地化文案工具。授权店铺或手动粘贴产品信息后，一键生成符合目标站点搜索与购物逻辑的多语言 Listing 文案（标题 / 五点 / 长描述 / 搜索词 / 建议关键词），并在合规校验通过后回填或导出。

> 本仓库为 **MVP 工程骨架**：后端可运行、前端可构建，SP-API 相关能力默认走「手动粘贴 + 导出」路径，规避个人开发者无法申请 SP-API 公共开发者资质的问题。

---

## 一、技术栈

| 层 | 选型 |
| --- | --- |
| 后端 | Python 3.11 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 |
| 前端 | Vue 3 · Vite · Element Plus · Pinia · Vue Router |
| 数据库 | PostgreSQL 15 · Alembic 迁移 |
| 任务调度 | APScheduler（规模化后可切 Celery + Redis） |
| LLM 网关 | 统一封装，支持 DeepSeek / OpenAI 多模型切换（Jinja2 Prompt） |
| 部署 | Docker Compose · Nginx |

---

## 二、目录结构

```
amazon-listing-mvp/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # 路由层：auth / listings / generate / billing
│   │   ├── core/            # 配置、DB、安全、日志、限流、异常
│   │   ├── models/          # ORM 模型：user/shop/listing/generation/subscription/compliance_rule
│   │   ├── repositories/    # 数据访问层
│   │   ├── schemas/         # Pydantic v2 请求/响应模型
│   │   ├── services/        # 业务层：llm / generation / compliance / export / spapi / billing
│   │   ├── prompts/         # Jinja2 Prompt 模板
│   │   ├── data/compliance_rules/  # 合规规则 JSON（按 marketplace 加载）
│   │   ├── tasks/           # APScheduler 调度
│   │   └── main.py          # FastAPI 入口
│   ├── alembic/             # 数据库迁移
│   ├── tests/               # pytest 单元测试
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/           # Dashboard / Login / ShopAuth / Generate / History / Billing / Settings
│   │   ├── components/      # 通用组件
│   │   ├── api/             # Axios 封装
│   │   ├── stores/          # Pinia
│   │   └── router/          # Vue Router
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml       # postgres + backend + frontend 一键起
├── AGENTS.md                # 工程约定（技术栈 / 硬约束 / 代码规范）
└── README.md
```

---

## 三、快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 准备后端环境变量
cp backend/.env.example backend/.env
#    编辑 backend/.env，至少填入 LLM_API_KEY；生产环境务必替换 JWT_SECRET 与 FERNET_KEY

# 2. 启动
docker compose up -d --build

# 3. 访问
#    前端：http://localhost
#    后端 API 文档：http://localhost:8000/docs
#    健康检查：http://localhost:8000/health
```

后端容器启动时会自动执行 `alembic upgrade head` 完成建表。

### 方式二：本地开发

```bash
# 后端
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                 # 修改 DATABASE_URL 指向本地 PG
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev                                          # http://localhost:5180
```

---

## 四、关键环境变量（backend/.env）

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接串（`postgresql+psycopg2://...`） |
| `JWT_SECRET` | JWT 签名密钥，**生产必须替换** |
| `FERNET_KEY` | 对称加密密钥，用于加密存储 SP-API refresh_token |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_BASE_URL` | LLM 网关配置（默认 DeepSeek） |
| `LLM_MODEL_STANDARD` / `LLM_MODEL_HIGH` | 标准 / 高质量模式所用模型 |
| `SPAPI_CLIENT_ID` / `SPAPI_CLIENT_SECRET` / `SPAPI_REFRESH_TOKEN` | SP-API 凭证，**MVP 可留空** |
| `FREE_MONTHLY_QUOTA` / `BASIC_MONTHLY_QUOTA` / `PRO_MONTHLY_QUOTA` | 各套餐月度额度 |

生成密钥示例：

```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
```

---

## 五、API 概览（前缀 `/api/v1`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/register` | 注册 |
| POST | `/auth/token` | 登录，返回 JWT |
| GET | `/auth/me` | 当前用户信息与配额 |
| GET | `/auth/spapi/authorize` · `/auth/spapi/callback` | SP-API 授权跳转 / 回调（可选） |
| GET | `/auth/shops` | 我的店铺列表 |
| POST / GET | `/listings` | 创建 / 查询 Listing |
| GET | `/listings/{listing_id}` | Listing 详情 |
| POST | `/listings/validate` | 独立合规校验 |
| POST | `/generate/listing` | 提交生成任务，返回 `task_id` |
| GET | `/generate/history` | 生成历史 |
| GET | `/generate/{task_id}` | 查询任务状态与生成结果 |
| GET | `/generate/{task_id}/export?format=xlsx\|json\|csv` | 导出（Excel 按亚马逊 Flat File 格式） |
| GET | `/billing/plans` | 套餐列表 |
| POST | `/billing/subscribe` | 创建订单 / 开通套餐 |
| GET | `/billing/usage` | 当前用量 |
| POST | `/billing/webhook` | 支付回调（预留） |

> 完整契约见运行后的 `/docs`（Swagger UI）。

---

## 六、合规与数据安全

1. **登录态与接口**：只能通过官方 Amazon SP-API 访问卖家数据，禁止模拟登录、禁止爬虫。
2. **人工确认回填**：生成结果默认不自动发布，必须先展示与现有 Listing 的差异、由用户确认后再回填。
3. **不采集 PII**：不收集买家个人隐私数据。
4. **境内存储**：数据存储在中国境内服务器。
5. **合规校验**：生成后自动校验禁用词、字符/字节限制、品牌侵权风险，规则位于 `backend/app/data/compliance_rules/*.json`，按 `marketplace` 加载，可按类目扩展。
6. **单人可维护**：不引入 Kubernetes / Kafka / 微服务集群等重型组件。

---

## 七、测试

```bash
cd backend
pytest -q
```

覆盖：认证、生成编排、LLM 网关、合规校验、导出、限流、安全、数据模型。

---

## 八、MVP 边界

**包含**：店铺授权（可选）、产品信息输入（手动粘贴 / 从 Listing 读取）、多语言文案生成、关键词优化、合规校验、回填与导出、账号与计费。

**不包含**：主图生成、广告文案、全自动批量铺货、竞品深度分析。

---

## 九、常见问题

**Q：为什么 SP-API 默认留空也能用？**
A：SP-API 公共开发者资质要求企业主体，个人开发者难以申请。MVP 走「手动粘贴产品信息 + 导出 Excel/JSON/CSV」的最小闭环，完全绕开授权卡点；后续拿到资质只需在 `.env` 补齐 SP-API 凭证并启用授权流程即可。

**Q：如何切换 LLM 模型？**
A：修改 `.env` 中的 `LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_MODEL_*`，所有调用统一经过 `app/services/llm_service.py` 网关，业务代码无需改动。

**Q：合规规则怎么扩展新类目？**
A：在 `app/data/compliance_rules/` 下按 marketplace 维护 JSON，键为类目名，值为禁用词与规则；新增即生效，无需改代码。
*（内容由AI生成，仅供参考）*
