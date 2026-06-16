from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import BaseModel, TimestampMixin, SoftDeleteMixin

user_role = Table(
    "user_roles",
    BaseModel.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)

role_permission = Table(
    "role_permissions",
    BaseModel.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id"), primary_key=True),
)


class User(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    avatar_url = Column(String(255))
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime)
    reset_token = Column(String(255))
    reset_token_expiry = Column(DateTime)

    roles = relationship("Role", secondary=user_role, back_populates="users")
    hospital = relationship("Hospital", back_populates="users")
    department = relationship("Department", back_populates="users")
    assigned_review_tasks = relationship("ReviewTask", foreign_keys="ReviewTask.assignee_id", back_populates="assignee")
    created_review_tasks = relationship("ReviewTask", foreign_keys="ReviewTask.creator_id", back_populates="creator")
    review_records = relationship("ReviewRecord", back_populates="reviewer")

    @property
    def role_names(self) -> list:
        return [role.name for role in self.roles]

    @property
    def permission_codes(self) -> set:
        permissions = set()
        for role in self.roles:
            for perm in role.permissions:
                permissions.add(perm.code)
        return permissions

    def has_permission(self, permission_code: str) -> bool:
        if self.is_superuser:
            return True
        return permission_code in self.permission_codes

    def has_role(self, role_name: str) -> bool:
        if self.is_superuser:
            return True
        return role_name in self.role_names


class Role(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "roles"

    name = Column(String(50), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(255))
    is_system = Column(Boolean, default=False, nullable=False)

    users = relationship("User", secondary=user_role, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permission, back_populates="roles")


class Permission(BaseModel, TimestampMixin):
    __tablename__ = "permissions"

    name = Column(String(100), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255))
    module = Column(String(50), index=True)

    roles = relationship("Role", secondary=role_permission, back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("code", name="uq_permission_code"),
    )
