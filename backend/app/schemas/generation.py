"""生成任务相关 Pydantic 模型。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.listing import SourceContent, Violation


class GenerateRequest(BaseModel):
    shop_id: Optional[int] = None
    listing_id: Optional[int] = None
    source_content: SourceContent = Field(default_factory=SourceContent)
    target_marketplaces: List[str] = Field(default_factory=lambda: ["US"])
    category: str = "*"
    tone: str = "professional"
    quality: str = "standard"  # standard | high


class ComplianceReport(BaseModel):
    passed: bool = True
    violations: List[Violation] = Field(default_factory=list)


class GeneratedListing(BaseModel):
    target_marketplace: str
    target_language: str
    title: str = ""
    bullets: List[str] = Field(default_factory=list)
    description: str = ""
    search_terms: str = ""
    suggested_keywords: List[str] = Field(default_factory=list)
    compliance_report: ComplianceReport = Field(default_factory=ComplianceReport)
    model_used: str = ""


class GenerateTaskResponse(BaseModel):
    task_id: str
    status: str = "pending"
    message: str = "任务已提交，请通过 /generate/{task_id} 查询进度"


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    status: str
    listing_id: Optional[int] = None
    results: List[GeneratedListing] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    errors: List[str] = Field(default_factory=list)


class GenerationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: str
    listing_id: Optional[int]
    target_marketplace: str
    target_language: str
    model_used: str
    result: Dict[str, Any]
    status: str
    created_at: datetime
