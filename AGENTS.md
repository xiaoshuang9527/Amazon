---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 727a7970f4b7df79363f5322a4753fc9_f9dd6ec5c38611f197eb525400393706
    ReservedCode1: mVHza60u5Vfl50Cs+gX+qI5o5AG/njB4YneneLt70SVI7N2KnQQSnE0KX0GITiU9nHJbzeUQxcM6XxHv5GhjvcCC8CWcumLAyfVjVs/oL7B9ikNZb/MiMU6LshQ1aDcP8qVvPr4L4+cvKDTbd+9OotbMBoxQ0n5q2ZvizXy1UciT3RIY8A5cSuy2ous=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 727a7970f4b7df79363f5322a4753fc9_f9dd6ec5c38611f197eb525400393706
    ReservedCode2: mVHza60u5Vfl50Cs+gX+qI5o5AG/njB4YneneLt70SVI7N2KnQQSnE0KX0GITiU9nHJbzeUQxcM6XxHv5GhjvcCC8CWcumLAyfVjVs/oL7B9ikNZb/MiMU6LshQ1aDcP8qVvPr4L4+cvKDTbd+9OotbMBoxQ0n5q2ZvizXy1UciT3RIY8A5cSuy2ous=
---

# 项目：亚马逊 Listing 多语言文案生成工具

## 产品定位
面向中国亚马逊多站点卖家的 AI Listing 本地化文案工具。授权店铺后，一键把中文/单一语言的产品信息生成符合目标站点搜索与购物逻辑的多语言 Listing 文案，并可回填或导出。

## 技术栈（固定，不要替换）
- 后端：Python 3.11 + FastAPI + SQLAlchemy 2.0 + Pydantic v2
- 前端：Vue 3 + Vite + Element Plus + Pinia
- 数据库：PostgreSQL 15
- 任务队列：冷启动用 APScheduler，规模化后切 Celery + Redis
- 部署：Docker Compose + Nginx，单机可跑
- LLM 接入：统一网关封装，支持 DeepSeek / OpenAI 多模型切换

## 硬约束
1. 只用官方 Amazon SP-API，禁止模拟登录、禁止爬虫抓取卖家后台。
2. 生成结果默认“需人工确认后回填”，不自动发布。
3. 不采集买家个人隐私数据（PII）。
4. 数据存储在中国境内服务器。
5. 单人可维护：禁止引入 Kubernetes、Kafka、微服务集群等重型组件。
6. 所有 LLM 调用必须经过统一网关，便于切换模型与灰度。

## 代码规范
- 后端分层：api / service / repository / model / schema
- 所有外部 API 调用必须有重试、超时、速率控制（令牌桶 + 指数退避）
- 所有 LLM Prompt 放在 prompts/ 目录，禁止硬编码在业务逻辑里
- 环境变量用 .env + pydantic-settings 管理，禁止硬编码密钥
- 每个模块必须有对应的 pytest 单元测试

## 交付节奏
按 MVP 范围交付，不做范围蔓延。MVP 包含：店铺授权、产品信息输入、多语言文案生成、关键词优化、合规校验、回填与导出、账号与计费。
MVP 不做：主图生成、广告文案、全自动批量铺货、竞品深度分析。
*（内容由AI生成，仅供参考）*
