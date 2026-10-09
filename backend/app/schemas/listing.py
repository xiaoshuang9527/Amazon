"""Listing 相关 Pydantic 模型。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceContent(BaseModel):
    """产品原始信息（手动粘贴或从 SP-API 读取）。"""

    title: str = Field(default="", max_length=2000)
    bullets: List[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=20000)
    keywords: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ListingCreate(BaseModel):
    shop_id: Optional[int] = None
    asin: Optional[str] = None
    sku: Optional[str] = None
    marketplace_id: Optional[str] = None
    source_language: str = "zh"
    source_content: SourceContent = Field(default_factory=SourceContent)


class ListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: Optional[int]
    asin: Optional[str]
    sku: Optional[str]
    marketplace_id: Optional[str]
    source_language: str
    source_content: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ValidateRequest(BaseModel):
    """合规校验请求。"""

    marketplace_id: str = Field(min_length=2, max_length=8)
    category: str = "*"
    title: str = ""
    bullets: List[str] = Field(default_factory=list)
    description: str = ""
    search_terms: str = ""
    brand_words: List[str] = Field(default_factory=list)


class Violation(BaseModel):
    type: str
    word: str = ""
    field: str = ""
    position: int = -1
    message: str = ""
    suggestion: str = ""


class ValidateResponse(BaseModel):
    passed: bool
    violations: List[Violation] = Field(default_factory=list)
