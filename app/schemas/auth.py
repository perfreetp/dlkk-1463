from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    full_name: str = Field(..., max_length=100, description="姓名")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    hospital_id: Optional[int] = Field(None, description="所属院区ID")
    department_id: Optional[int] = Field(None, description="所属科室ID")
    avatar_url: Optional[str] = Field(None, description="头像URL")

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    role_ids: Optional[List[int]] = Field(None, description="角色ID列表")


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    hospital_id: Optional[int] = None
    department_id: Optional[int] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None
    role_ids: Optional[List[int]] = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    roles: Optional[List[dict]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    hospital_name: Optional[str] = None
    department_name: Optional[str] = None
    is_active: bool
    roles: List[str] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码")
    confirm_password: str = Field(..., min_length=6, max_length=50, description="确认密码")


class RoleBase(BaseModel):
    name: str = Field(..., max_length=50, description="角色名称")
    code: str = Field(..., max_length=50, description="角色编码")
    description: Optional[str] = Field(None, max_length=255, description="角色描述")

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = Field(None, description="权限ID列表")


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    permission_ids: Optional[List[int]] = None

    model_config = ConfigDict(from_attributes=True)


class RoleResponse(RoleBase):
    id: int
    is_system: bool
    permissions: Optional[List[dict]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PermissionBase(BaseModel):
    name: str = Field(..., max_length=100, description="权限名称")
    code: str = Field(..., max_length=100, description="权限编码")
    description: Optional[str] = Field(None, max_length=255, description="权限描述")
    module: Optional[str] = Field(None, max_length=50, description="所属模块")

    model_config = ConfigDict(from_attributes=True)


class PermissionResponse(PermissionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
