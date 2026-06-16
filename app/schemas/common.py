from typing import Generic, TypeVar, Optional, List, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    success: bool = True
    message: str = "操作成功"
    data: Optional[T] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


ApiResponse = ResponseModel


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "查询成功"
    data: List[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class DateRangeParams(BaseModel):
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")


class SortParams(BaseModel):
    sort_by: Optional[str] = Field(None, description="排序字段")
    sort_order: Optional[str] = Field("desc", description="排序方向: asc/desc")

    def get_order_by(self, model_class: Any) -> Optional[Any]:
        if not self.sort_by:
            return None

        field = getattr(model_class, self.sort_by, None)
        if field is None:
            return None

        if self.sort_order and self.sort_order.lower() == "desc":
            return field.desc()
        return field.asc()
