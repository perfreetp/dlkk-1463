from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class RuleCategoryBase(BaseModel):
    code: str = Field(..., max_length=50, description="分类编码")
    name: str = Field(..., max_length=100, description="分类名称")
    parent_id: Optional[int] = Field(None, description="父分类ID")
    description: Optional[str] = Field(None, description="描述")
    sort_order: Optional[int] = Field(0, description="排序")
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class RuleCategoryCreate(RuleCategoryBase):
    pass


class RuleCategoryUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=100)
    parent_id: Optional[int] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class RuleCategoryResponse(RuleCategoryBase):
    id: int
    children: Optional[List["RuleCategoryResponse"]] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityRuleBase(BaseModel):
    category_id: int = Field(..., description="分类ID")

    code: str = Field(..., max_length=100, description="规则编码")
    name: str = Field(..., max_length=200, description="规则名称")
    rule_type: str = Field(..., max_length=50, description="规则类型")

    description: Optional[str] = Field(None, description="规则描述")
    rule_logic: Optional[str] = Field(None, description="规则逻辑")
    rule_params: Optional[Dict[str, Any]] = Field(None, description="规则参数")

    severity_level: Optional[str] = Field("medium", max_length=20, description="严重程度")
    risk_score: Optional[int] = Field(5, description="风险分值")

    condition_expression: Optional[str] = Field(None, description="条件表达式")
    threshold_value: Optional[str] = Field(None, max_length=100, description="阈值")
    threshold_operator: Optional[str] = Field(None, max_length=20, description="阈值操作符")

    applicable_hospitals: Optional[List[int]] = Field(None, description="适用院区")
    effective_date: Optional[str] = Field(None, max_length=20, description="生效日期")
    expiry_date: Optional[str] = Field(None, max_length=20, description="失效日期")

    version: Optional[str] = Field("1.0", max_length=20, description="版本")
    is_active: bool = True
    is_standard: Optional[bool] = Field(False, description="是否集团标准")

    model_config = ConfigDict(from_attributes=True)


class QualityRuleCreate(QualityRuleBase):
    pass


class QualityRuleUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = Field(None, max_length=200)
    rule_type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    rule_logic: Optional[str] = None
    rule_params: Optional[Dict[str, Any]] = None
    severity_level: Optional[str] = Field(None, max_length=20)
    risk_score: Optional[int] = None
    condition_expression: Optional[str] = None
    threshold_value: Optional[str] = Field(None, max_length=100)
    threshold_operator: Optional[str] = Field(None, max_length=20)
    applicable_hospitals: Optional[List[int]] = None
    is_active: Optional[bool] = None
    is_standard: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class QualityRuleResponse(QualityRuleBase):
    id: int
    category_name: Optional[str] = None
    failure_count: Optional[int] = 0
    pass_count: Optional[int] = 0
    created_by: Optional[int] = None
    approved_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QualityRuleTestRequest(BaseModel):
    rule_id: int = Field(..., description="规则ID")
    test_data: Dict[str, Any] = Field(..., description="测试数据")

    model_config = ConfigDict(from_attributes=True)


class QualityRuleTestResult(BaseModel):
    rule_id: int
    rule_name: str
    test_result: bool
    match_details: Optional[str] = None
    execution_time_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


RuleCategoryResponse.model_rebuild()
