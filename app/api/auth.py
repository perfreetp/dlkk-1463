from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.deps import get_current_user, require_permission, require_roles
from ..core.security import oauth2_scheme
from ..models import User
from ..schemas import (
    UserCreate,
    UserUpdate,
    UserLogin,
    UserResponse,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    PermissionCreate,
    PermissionResponse,
    ChangePasswordRequest,
    ResetPasswordRequest,
    LoginResponse,
    ApiResponse,
    PaginationParams,
)
from ..services import AuthService
from ..core.utils import paginate

router = APIRouter()


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    result = auth_service.login(login_data)
    return ApiResponse(data=result, message="登录成功")


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    auth_service.logout(current_user.id)
    return ApiResponse(data={"success": True}, message="退出登录成功")


@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    auth_service = AuthService(db)
    user = auth_service.register_user(user_data, created_by=current_user.id)
    return ApiResponse(data=UserResponse.model_validate(user), message="注册成功")


@router.post("/change-password", response_model=ApiResponse[dict])
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    auth_service.change_password(current_user.id, request)
    return ApiResponse(data={"success": True}, message="密码修改成功")


@router.post("/reset-password-request", response_model=ApiResponse[dict])
async def reset_password_request(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_service = AuthService(db)
    result = auth_service.reset_password_request(request)
    return ApiResponse(data=result, message="重置密码链接已发送")


@router.post("/reset-password-confirm", response_model=ApiResponse[dict])
async def reset_password_confirm(
    token: str,
    new_password: str,
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    auth_service.reset_password_confirm(token, new_password)
    return ApiResponse(data={"success": True}, message="密码重置成功")


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = auth_service.get_current_user_profile(current_user.id)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.get("/me/permissions", response_model=ApiResponse[List[str]])
async def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    permissions = auth_service.get_user_permissions(current_user.id)
    return ApiResponse(data=permissions)


@router.get("/me/workload", response_model=ApiResponse[dict])
async def get_my_workload(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    workload = auth_service.get_user_workload(current_user.id)
    return ApiResponse(data=workload)


@router.get("/users", response_model=ApiResponse[dict])
@require_permission("user:read")
async def list_users(
    hospital_id: Optional[int] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    keyword: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    users, total = auth_service.list_users(
        hospital_id=hospital_id,
        role_id=role_id,
        is_active=is_active,
        keyword=keyword,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate([UserResponse.model_validate(u) for u in users], total, pagination))


@router.get("/users/{user_id}", response_model=ApiResponse[UserResponse])
@require_permission("user:read")
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = auth_service.get_user(user_id)
    return ApiResponse(data=UserResponse.model_validate(user))


@router.put("/users/{user_id}", response_model=ApiResponse[UserResponse])
@require_permission("user:update")
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = auth_service.update_user(user_id, update_data, operator_id=current_user.id)
    return ApiResponse(data=UserResponse.model_validate(user), message="用户信息更新成功")


@router.patch("/users/{user_id}/toggle-active", response_model=ApiResponse[UserResponse])
@require_permission("user:manage")
async def toggle_user_active(
    user_id: int,
    is_active: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = auth_service.toggle_user_active(user_id, is_active, operator_id=current_user.id)
    return ApiResponse(data=UserResponse.model_validate(user), message="用户状态更新成功")


@router.patch("/users/{user_id}/unlock", response_model=ApiResponse[UserResponse])
@require_permission("user:manage")
async def unlock_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = auth_service.unlock_user(user_id, operator_id=current_user.id)
    return ApiResponse(data=UserResponse.model_validate(user), message="用户解锁成功")


@router.get("/users/{user_id}/workload", response_model=ApiResponse[dict])
@require_permission("user:read")
async def get_user_workload(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    workload = auth_service.get_user_workload(user_id)
    return ApiResponse(data=workload)


@router.post("/users/{user_id}/roles/{role_id}", response_model=ApiResponse[UserResponse])
@require_permission("user:manage")
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = auth_service.assign_role_to_user(user_id, role_id)
    return ApiResponse(data=UserResponse.model_validate(user), message="角色分配成功")


@router.delete("/users/{user_id}/roles/{role_id}", response_model=ApiResponse[UserResponse])
@require_permission("user:manage")
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    user = auth_service.remove_role_from_user(user_id, role_id)
    return ApiResponse(data=UserResponse.model_validate(user), message="角色移除成功")


@router.get("/roles", response_model=ApiResponse[dict])
@require_permission("role:read")
async def list_roles(
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    roles, total = auth_service.list_roles(is_active=is_active, skip=pagination.skip, limit=pagination.limit)
    return ApiResponse(data=paginate([RoleResponse.model_validate(r) for r in roles], total, pagination))


@router.post("/roles", response_model=ApiResponse[RoleResponse])
@require_permission("role:create")
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    role = auth_service.create_role(role_data, created_by=current_user.id)
    return ApiResponse(data=RoleResponse.model_validate(role), message="角色创建成功")


@router.get("/roles/{role_id}", response_model=ApiResponse[RoleResponse])
@require_permission("role:read")
async def get_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    role = auth_service.get_role(role_id)
    return ApiResponse(data=RoleResponse.model_validate(role))


@router.put("/roles/{role_id}", response_model=ApiResponse[RoleResponse])
@require_permission("role:update")
async def update_role(
    role_id: int,
    update_data: RoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    role = auth_service.update_role(role_id, update_data, operator_id=current_user.id)
    return ApiResponse(data=RoleResponse.model_validate(role), message="角色更新成功")


@router.post("/roles/{role_id}/permissions/{permission_id}", response_model=ApiResponse[RoleResponse])
@require_permission("role:manage")
async def assign_permission_to_role(
    role_id: int,
    permission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    role = auth_service.assign_permission_to_role(role_id, permission_id)
    return ApiResponse(data=RoleResponse.model_validate(role), message="权限分配成功")


@router.delete("/roles/{role_id}/permissions/{permission_id}", response_model=ApiResponse[RoleResponse])
@require_permission("role:manage")
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    role = auth_service.remove_permission_from_role(role_id, permission_id)
    return ApiResponse(data=RoleResponse.model_validate(role), message="权限移除成功")


@router.get("/permissions", response_model=ApiResponse[dict])
@require_permission("permission:read")
async def list_permissions(
    module: Optional[str] = None,
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    permissions, total = auth_service.list_permissions(
        module=module,
        is_active=is_active,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate([PermissionResponse.model_validate(p) for p in permissions], total, pagination))


@router.post("/permissions", response_model=ApiResponse[PermissionResponse])
@require_permission("permission:create")
async def create_permission(
    permission_data: PermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    permission = auth_service.create_permission(permission_data, created_by=current_user.id)
    return ApiResponse(data=PermissionResponse.model_validate(permission), message="权限创建成功")


@router.get("/users/workload/all", response_model=ApiResponse[List[dict]])
@require_permission("user:read")
async def get_all_users_workload(
    hospital_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    workloads = auth_service.get_all_users_workload(hospital_id=hospital_id)
    return ApiResponse(data=workloads)
