"""聚合 v1 下所有路由。"""

from fastapi import APIRouter

from app.api.v1 import admin, auth, billing, generate, listings

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证与授权"])
api_router.include_router(listings.router, prefix="/listings", tags=["Listing"])
api_router.include_router(generate.router, prefix="/generate", tags=["文案生成"])
api_router.include_router(billing.router, prefix="/billing", tags=["计费与订阅"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理后台"])
