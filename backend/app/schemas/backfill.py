"""回填（diff / apply）相关 Pydantic 模型。"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.schemas.generation import ComplianceReport


class DiffField(BaseModel):
    """单个可回填字段的差异。"""

    field: str
    label: str
    current: Any = None
    proposed: Any = None
    changed: bool = False
    editable: bool = True


class ListingDiffResponse(BaseModel):
    listing_id: int
    marketplace_id: str
    task_id: str
    # 当前文案来源：listing_copy（上次回填结果）| source_content（Listing 原始信息）
    current_source: str
    current_updated_at: Optional[datetime] = None
    model_used: str = ""
    target_language: str = ""
    generated_compliance_report: ComplianceReport = Field(default_factory=ComplianceReport)
    fields: List[DiffField] = Field(default_factory=list)


class FieldSelection(BaseModel):
    """用户对单个字段的勾选结果。"""

    field: str
    selected: bool = True
    # 允许用户在前端微调后提交；为空则采用生成结果
    value: Optional[Any] = None


class ApplyRequest(BaseModel):
    task_id: str = Field(min_length=1)
    marketplace_id: str = Field(min_length=2, max_length=8)
    selections: List[FieldSelection] = Field(default_factory=list)
    # 合规校验未通过时是否强制回填
    force: bool = False


class ApplyResponse(BaseModel):
    listing_id: int
    marketplace_id: str
    task_id: str
    applied_fields: List[str] = Field(default_factory=list)
    skipped_fields: List[str] = Field(default_factory=list)
    compliance_report: ComplianceReport = Field(default_factory=ComplianceReport)
    forced: bool = False
    spapi_synced: bool = False
    message: str = ""
    applied_at: Optional[datetime] = None
    content: dict = Field(default_factory=dict)
