from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import random
import string

from ..models import User, Role, Permission, user_roles, role_permissions
from ..schemas import (
    UserCreate,
    UserUpdate,
    UserLogin,
    UserResponse,
    RoleCreate,
    RoleUpdate,
    PermissionCreate,
    ChangePasswordRequest,
    ResetPasswordRequest,
    LoginResponse,
)
from ..core.exceptions import NotFoundError, BusinessError, ForbiddenError, AuthenticationError
from ..core.logger import get_logger
from ..core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_reset_token,
    verify_reset_token,
)
from ..core.utils import generate_random_string, clean_text

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, user_data: UserCreate, created_by: Optional[int] = None) -> User:
        existing = self.db.query(User).filter(
            User.username == user_data.username,
            User.is_deleted == False,
        ).first()
        if existing:
            raise BusinessError(f"用户名已存在: {user_data.username}")

        if user_data.email:
            existing_email = self.db.query(User).filter(
                User.email == user_data.email,
                User.is_deleted == False,
            ).first()
            if existing_email:
                raise BusinessError(f"邮箱已被使用: {user_data.email}")

        if user_data.phone:
            existing_phone = self.db.query(User).filter(
                User.phone == user_data.phone,
                User.is_deleted == False,
            ).first()
            if existing_phone:
                raise BusinessError(f"手机号已被使用: {user_data.phone}")

        user = User(**user_data.model_dump(exclude={"password", "role_ids"}))
        user.password_hash = get_password_hash(user_data.password)
        user.is_active = True
        user.created_by = created_by

        if user_data.role_ids:
            roles = self.db.query(Role).filter(
                Role.id.in_(user_data.role_ids),
                Role.is_deleted == False,
            ).all()
            user.roles = roles

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        logger.info(f"Registered user: {user.username} ({user.id})")
        return user

    def login(self, login_data: UserLogin) -> LoginResponse:
        user = self.db.query(User).filter(
            (User.username == login_data.username) | (User.email == login_data.username),
            User.is_deleted == False,
        ).first()

        if not user:
            user = self.db.query(User).filter(
                or_(
                    User.username == login_data.username,
                    User.email == login_data.username,
                ),
                User.is_deleted == False,
            ).first()

        if not user:
            user = self.db.query(User).filter(
                User.username == login_data.username,
                User.is_deleted == False,
            ).first()

        if not user and login_data.username and "@" in login_data.username:
            user = self.db.query(User).filter(
                User.email == login_data.username,
                User.is_deleted == False,
            ).first()

        if not user:
            raise AuthenticationError("用户名或密码错误")

        if not user.is_active:
            raise AuthenticationError("账号已被禁用")

        if not verify_password(login_data.password, user.password_hash):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                user.is_locked = True
                user.locked_at = datetime.utcnow()
            self.db.commit()
            raise AuthenticationError("用户名或密码错误")

        if user.is_locked:
            raise AuthenticationError("账号已被锁定，请联系管理员")

        user.failed_login_attempts = 0
        user.last_login_at = datetime.utcnow()
        self.db.commit()

        extra_data = {
            "user_id": user.id,
            "username": user.username,
            "roles": [role.code for role in user.roles],
        }

        access_token = create_access_token(
            subject=str(user.id),
            extra_data=extra_data,
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
            roles=[role.code for role in user.roles],
            permissions=self._get_user_permissions(user),
        )

    def logout(self, user_id: int) -> None:
        user = self.db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False,
        ).first()
        if user:
            user.last_logout_at = datetime.utcnow()
            self.db.commit()
        logger.info(f"User logged out: {user_id}")

    def change_password(self, user_id: int, request: ChangePasswordRequest) -> None:
        user = self._get_user(user_id)

        if not verify_password(request.old_password, user.password_hash):
            raise BusinessError("原密码错误")

        if verify_password(request.new_password, user.password_hash):
            raise BusinessError("新密码不能与原密码相同")

        user.password_hash = get_password_hash(request.new_password)
        user.password_changed_at = datetime.utcnow()
        user.must_change_password = False

        self.db.commit()
        logger.info(f"Password changed for user: {user_id}")

    def reset_password_request(self, request: ResetPasswordRequest) -> Dict[str, Any]:
        user = self.db.query(User).filter(
            User.email == request.email,
            User.is_deleted == False,
        ).first()

        if not user:
            raise NotFoundError("用户不存在")

        if not user.is_active:
            raise BusinessError("账号已被禁用")

        reset_token = create_reset_token(user.email)
        user.reset_token = reset_token
        user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)

        self.db.commit()

        return {
            "message": "重置密码链接已发送到您的邮箱",
            "reset_token": reset_token,
        }

    def reset_password_confirm(self, token: str, new_password: str) -> None:
        email = verify_reset_token(token)
        if not email:
            raise BusinessError("重置链接已过期或无效")

        user = self.db.query(User).filter(
            User.email == email,
            User.reset_token == token,
            User.is_deleted == False,
        ).first()

        if not user:
            user = self.db.query(User).filter(
                User.email == email,
                User.is_deleted == False,
            ).first()

        if not user:
            raise NotFoundError("用户不存在")

        if user.reset_token_expires_at and user.reset_token_expires_at < datetime.utcnow():
            raise BusinessError("重置链接已过期")

        user.password_hash = get_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expires_at = None
        user.password_changed_at = datetime.utcnow()

        self.db.commit()
        logger.info(f"Password reset for user: {user.id}")

    def _get_user(self, user_id: int) -> User:
        user = self.db.query(User).filter(
            User.id == user_id,
            User.is_deleted == False,
        ).first()
        if not user:
            raise NotFoundError(f"用户不存在: {user_id}")
        return user

    def get_user(self, user_id: int) -> User:
        return self._get_user(user_id)

    def get_current_user_profile(self, user_id: int) -> UserResponse:
        user = self._get_user(user_id)
        return user

    def update_user(self, user_id: int, update_data: UserUpdate, operator_id: Optional[int] = None) -> User:
        user = self._get_user(user_id)

        update_dict = update_data.model_dump(exclude_unset=True, exclude={"role_ids"})

        for key, value in update_dict.items():
            setattr(user, key, value)

        if update_data.role_ids is not None:
            roles = self.db.query(Role).filter(
                Role.id.in_(update_data.role_ids),
                Role.is_deleted == False,
            ).all()
            user.roles = roles

        user.updated_by = operator_id
        user.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(user)
        return user

    def list_users(
        self,
        hospital_id: Optional[int] = None,
        role_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[User], int]:
        query = self.db.query(User).filter(User.is_deleted == False)

        if hospital_id:
            query = query.filter(User.hospital_id == hospital_id)
        if role_id:
            query = query.join(user_roles).filter(user_roles.c.role_id == role_id)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        if keyword:
            keyword = f"%{keyword}%"
            query = query.filter(
                or_(
                    User.username.ilike(keyword),
                    User.name.ilike(keyword),
                    User.email.ilike(keyword),
                )
            )

        total = query.count()
        users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
        return users, total

    def create_role(self, role_data: RoleCreate, created_by: Optional[int] = None) -> Role:
        existing = self.db.query(Role).filter(
            (Role.code == role_data.code) | (Role.name == role_data.name),
            Role.is_deleted == False,
        ).first()
        if existing:
            raise BusinessError(f"角色代码或名称已存在")

        role = Role(**role_data.model_dump(exclude={"permission_ids"}))
        role.created_by = created_by

        if role_data.permission_ids:
            permissions = self.db.query(Permission).filter(
                Permission.id.in_(role_data.permission_ids),
                Permission.is_deleted == False,
            ).all()
            role.permissions = permissions

        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)

        logger.info(f"Created role: {role.name} ({role.id})")
        return role

    def update_role(self, role_id: int, update_data: RoleUpdate, operator_id: Optional[int] = None) -> Role:
        role = self.db.query(Role).filter(
            Role.id == role_id,
            Role.is_deleted == False,
        ).first()
        if not role:
            raise NotFoundError(f"角色不存在: {role_id}")

        update_dict = update_data.model_dump(exclude_unset=True, exclude={"permission_ids"})
        for key, value in update_dict.items():
            setattr(role, key, value)

        if update_data.permission_ids is not None:
            permissions = self.db.query(Permission).filter(
                Permission.id.in_(update_data.permission_ids),
                Permission.is_deleted == False,
            ).all()
            role.permissions = permissions

        role.updated_by = operator_id
        role.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(role)
        return role

    def list_roles(
        self,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Role], int]:
        query = self.db.query(Role).filter(Role.is_deleted == False)

        if is_active is not None:
            query = query.filter(Role.is_active == is_active)

        total = query.count()
        roles = query.order_by(Role.created_at.desc()).offset(skip).limit(limit).all()
        return roles, total

    def get_role(self, role_id: int) -> Role:
        role = self.db.query(Role).filter(
            Role.id == role_id,
            Role.is_deleted == False,
        ).first()
        if not role:
            raise NotFoundError(f"角色不存在: {role_id}")
        return role

    def create_permission(self, permission_data: PermissionCreate, created_by: Optional[int] = None) -> Permission:
        existing = self.db.query(Permission).filter(
            (Permission.code == permission_data.code) | (Permission.name == permission_data.name),
            Permission.is_deleted == False,
        ).first()
        if existing:
            raise BusinessError(f"权限代码或名称已存在")

        permission = Permission(**permission_data.model_dump())
        permission.created_by = created_by

        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)

        logger.info(f"Created permission: {permission.name} ({permission.id})")
        return permission

    def list_permissions(
        self,
        module: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Permission], int]:
        query = self.db.query(Permission).filter(Permission.is_deleted == False)

        if module:
            query = query.filter(Permission.module == module)
        if is_active is not None:
            query = query.filter(Permission.is_active == is_active)

        total = query.count()
        permissions = query.order_by(Permission.module, Permission.code).offset(skip).limit(limit).all()
        return permissions, total

    def _get_user_permissions(self, user: User) -> List[str]:
        permission_codes = set()
        for role in user.roles:
            for perm in role.permissions:
                permission_codes.add(perm.code)
        return list(permission_codes)

    def get_user_permissions(self, user_id: int) -> List[str]:
        user = self._get_user(user_id)
        return self._get_user_permissions(user)

    def check_user_permission(self, user_id: int, permission_code: str) -> bool:
        permissions = self.get_user_permissions(user_id)
        return permission_code in permissions

    def check_user_role(self, user_id: int, *role_codes: Tuple[str, ...]) -> bool:
        user = self._get_user(user_id)
        user_role_codes = [role.code for role in user.roles]
        return any(role in user_role_codes for role in role_codes)

    def toggle_user_active(self, user_id: int, is_active: bool, operator_id: Optional[int] = None) -> User:
        user = self._get_user(user_id)
        user.is_active = is_active
        user.updated_by = operator_id
        user.updated_at = datetime.utcnow()

        if not is_active:
            user.deactivated_at = datetime.utcnow()
            user.deactivated_by = operator_id

        self.db.commit()
        self.db.refresh(user)
        return user

    def unlock_user(self, user_id: int, operator_id: Optional[int] = None) -> User:
        user = self._get_user(user_id)
        user.is_locked = False
        user.failed_login_attempts = 0
        user.locked_at = None
        user.updated_by = operator_id
        user.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_workload(self, user_id: int) -> Dict[str, Any]:
        from .review_service import ReviewService
        review_service = ReviewService(self.db)
        return review_service.get_user_workload(user_id)

    def get_all_users_workload(
        self,
        hospital_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        from .review_service import ReviewService
        review_service = ReviewService(self.db)

        query = self.db.query(User).filter(
            User.is_deleted == False,
            User.is_active == True,
        )

        if hospital_id:
            query = query.filter(User.hospital_id == hospital_id)

        users = query.all()

        workload_list = []
        for user in users:
            workload = review_service.get_user_workload(user.id)
            workload_list.append({
                "user_id": user.id,
                "username": user.username,
                "name": user.name,
                "hospital_id": user.hospital_id,
                **workload,
            })

        return workload_list

    def assign_role_to_user(self, user_id: int, role_id: int) -> User:
        user = self._get_user(user_id)
        role = self.db.query(Role).filter(
            Role.id == role_id,
            Role.is_deleted == False,
        ).first()
        if not role:
            raise NotFoundError(f"角色不存在: {role_id}")

        if role not in user.roles:
            user.roles.append(role)
            self.db.commit()
            self.db.refresh(user)

        return user

    def remove_role_from_user(self, user_id: int, role_id: int) -> User:
        user = self._get_user(user_id)
        role = self.db.query(Role).filter(
            Role.id == role_id,
            Role.is_deleted == False,
        ).first()
        if not role:
            raise NotFoundError(f"角色不存在: {role_id}")

        if role in user.roles:
            user.roles.remove(role)
            self.db.commit()
            self.db.refresh(user)

        return user

    def assign_permission_to_role(self, role_id: int, permission_id: int) -> Role:
        role = self.get_role(role_id)
        permission = self.db.query(Permission).filter(
            Permission.id == permission_id,
            Permission.is_deleted == False,
        ).first()
        if not permission:
            raise NotFoundError(f"权限不存在: {permission_id}")

        if permission not in role.permissions:
            role.permissions.append(permission)
            self.db.commit()
            self.db.refresh(role)

        return role

    def remove_permission_from_role(self, role_id: int, permission_id: int) -> Role:
        role = self.get_role(role_id)
        permission = self.db.query(Permission).filter(
            Permission.id == permission_id,
            Permission.is_deleted == False,
        ).first()
        if not permission:
            raise NotFoundError(f"权限不存在: {permission_id}")

        if permission in role.permissions:
            role.permissions.remove(permission)
            self.db.commit()
            self.db.refresh(role)

        return role
