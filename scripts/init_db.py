import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import User, Role, Permission
from app.core.security import get_password_hash
from app.core.logger import logger

PERMISSIONS = [
    {"code": "user:read", "name": "查看用户", "module": "用户管理", "description": "查看用户信息"},
    {"code": "user:create", "name": "创建用户", "module": "用户管理", "description": "创建新用户"},
    {"code": "user:update", "name": "更新用户", "module": "用户管理", "description": "更新用户信息"},
    {"code": "user:manage", "name": "管理用户", "module": "用户管理", "description": "用户状态管理、角色分配"},
    {"code": "role:read", "name": "查看角色", "module": "角色管理", "description": "查看角色信息"},
    {"code": "role:create", "name": "创建角色", "module": "角色管理", "description": "创建新角色"},
    {"code": "role:update", "name": "更新角色", "module": "角色管理", "description": "更新角色信息"},
    {"code": "role:manage", "name": "管理角色", "module": "角色管理", "description": "角色权限分配"},
    {"code": "permission:read", "name": "查看权限", "module": "权限管理", "description": "查看权限列表"},
    {"code": "permission:create", "name": "创建权限", "module": "权限管理", "description": "创建新权限"},
    {"code": "examination:read", "name": "查看检查", "module": "检查数据", "description": "查看检查记录"},
    {"code": "examination:create", "name": "创建检查", "module": "检查数据", "description": "录入检查数据"},
    {"code": "examination:update", "name": "更新检查", "module": "检查数据", "description": "更新检查信息"},
    {"code": "examination:manage", "name": "管理检查", "module": "检查数据", "description": "批量处理、自动QA"},
    {"code": "rule:read", "name": "查看规则", "module": "规则管理", "description": "查看质控规则"},
    {"code": "rule:create", "name": "创建规则", "module": "规则管理", "description": "创建质控规则"},
    {"code": "rule:update", "name": "更新规则", "module": "规则管理", "description": "更新质控规则"},
    {"code": "rule:manage", "name": "管理规则", "module": "规则管理", "description": "规则测试、发布、启停"},
    {"code": "anomaly:read", "name": "查看异常", "module": "异常管理", "description": "查看异常记录"},
    {"code": "anomaly:detect", "name": "检测异常", "module": "异常管理", "description": "执行异常检测"},
    {"code": "anomaly:update", "name": "更新异常", "module": "异常管理", "description": "更新异常状态"},
    {"code": "review:read", "name": "查看复核", "module": "复核流转", "description": "查看复核任务"},
    {"code": "review:create", "name": "创建复核", "module": "复核流转", "description": "创建复核任务"},
    {"code": "review:update", "name": "更新复核", "module": "复核流转", "description": "更新复核任务"},
    {"code": "review:assign", "name": "分配复核", "module": "复核流转", "description": "分配复核任务"},
    {"code": "review:operate", "name": "操作复核", "module": "复核流转", "description": "接受/拒绝/提交复核"},
    {"code": "review:verify", "name": "验证整改", "module": "复核流转", "description": "验证整改结果"},
    {"code": "review:statistics", "name": "复核统计", "module": "复核流转", "description": "查看复核统计数据"},
    {"code": "statistics:read", "name": "查看统计", "module": "统计报送", "description": "查看统计数据"},
    {"code": "statistics:manage", "name": "管理统计", "module": "统计报送", "description": "生成月报"},
    {"code": "statistics:export", "name": "导出统计", "module": "统计报送", "description": "导出统计数据"},
    {"code": "benchmark:read", "name": "查看对标", "module": "院区对标", "description": "查看对标数据"},
    {"code": "benchmark:manage", "name": "管理对标", "module": "院区对标", "description": "生成对标数据、管理案例"},
    {"code": "benchmark:export", "name": "导出对标", "module": "院区对标", "description": "导出对标数据"},
    {"code": "scheduler:read", "name": "查看调度", "module": "任务调度", "description": "查看定时任务"},
    {"code": "scheduler:manage", "name": "管理调度", "module": "任务调度", "description": "创建、更新、执行定时任务"},
]

ROLES = [
    {
        "name": "超级管理员",
        "code": "super_admin",
        "description": "系统超级管理员，拥有所有权限",
        "is_active": True,
        "permissions": [p["code"] for p in PERMISSIONS],
    },
    {
        "name": "集团质控主任",
        "code": "group_quality_director",
        "description": "集团质控中心主任，管理全院质控工作",
        "is_active": True,
        "permissions": [
            "examination:read", "examination:manage",
            "rule:read", "rule:create", "rule:update", "rule:manage",
            "anomaly:read", "anomaly:detect",
            "review:read", "review:create", "review:assign", "review:statistics",
            "statistics:read", "statistics:manage", "statistics:export",
            "benchmark:read", "benchmark:manage", "benchmark:export",
            "scheduler:read", "scheduler:manage",
            "user:read", "role:read", "permission:read",
        ],
    },
    {
        "name": "院区质控员",
        "code": "hospital_quality_officer",
        "description": "院区质控员，负责本院区质控复核工作",
        "is_active": True,
        "permissions": [
            "examination:read", "examination:create", "examination:update",
            "anomaly:read",
            "review:read", "review:create", "review:update", "review:operate",
            "statistics:read",
        ],
    },
    {
        "name": "放射科主任",
        "code": "radiology_director",
        "description": "放射科主任，查看本科室质控数据",
        "is_active": True,
        "permissions": [
            "examination:read",
            "anomaly:read",
            "review:read",
            "statistics:read",
            "benchmark:read",
        ],
    },
    {
        "name": "数据分析师",
        "code": "data_analyst",
        "description": "数据分析师，负责统计分析和报告生成",
        "is_active": True,
        "permissions": [
            "examination:read",
            "anomaly:read",
            "review:read", "review:statistics",
            "statistics:read", "statistics:manage", "statistics:export",
            "benchmark:read", "benchmark:export",
        ],
    },
]

DEFAULT_USERS = [
    {
        "username": "admin",
        "email": "admin@hospital-group.com",
        "real_name": "系统管理员",
        "password": "Admin@123456",
        "phone": "13800138000",
        "employee_id": "SYS001",
        "role_codes": ["super_admin"],
    },
    {
        "username": "qcdirector",
        "email": "qcdirector@hospital-group.com",
        "real_name": "张主任",
        "password": "Quality@2024",
        "phone": "13800138001",
        "employee_id": "QC001",
        "role_codes": ["group_quality_director"],
    },
    {
        "username": "qc_officer1",
        "email": "qc_officer1@hospital1.com",
        "real_name": "李质控",
        "password": "Qc@123456",
        "phone": "13800138002",
        "employee_id": "QC101",
        "role_codes": ["hospital_quality_officer"],
    },
]


def init_database():
    db = SessionLocal()
    try:
        logger.info("开始初始化数据库...")
        
        existing_permissions = {p.code: p for p in db.query(Permission).all()}
        for perm_data in PERMISSIONS:
            if perm_data["code"] not in existing_permissions:
                perm = Permission(**perm_data)
                db.add(perm)
                logger.info(f"创建权限: {perm_data['code']} - {perm_data['name']}")
            else:
                existing = existing_permissions[perm_data["code"]]
                existing.name = perm_data["name"]
                existing.module = perm_data["module"]
                existing.description = perm_data["description"]
        db.commit()
        logger.info(f"权限初始化完成，共 {len(PERMISSIONS)} 个权限")
        
        all_permissions = {p.code: p for p in db.query(Permission).all()}
        
        existing_roles = {r.code: r for r in db.query(Role).all()}
        for role_data in ROLES:
            perm_codes = role_data.pop("permissions")
            if role_data["code"] not in existing_roles:
                role = Role(**role_data)
                for code in perm_codes:
                    if code in all_permissions:
                        role.permissions.append(all_permissions[code])
                db.add(role)
                logger.info(f"创建角色: {role_data['code']} - {role_data['name']}")
            else:
                existing = existing_roles[role_data["code"]]
                existing.name = role_data["name"]
                existing.description = role_data["description"]
                existing.is_active = role_data["is_active"]
                existing.permissions.clear()
                for code in perm_codes:
                    if code in all_permissions:
                        existing.permissions.append(all_permissions[code])
                logger.info(f"更新角色: {role_data['code']} - {role_data['name']}")
        db.commit()
        logger.info(f"角色初始化完成，共 {len(ROLES)} 个角色")
        
        all_roles = {r.code: r for r in db.query(Role).all()}
        
        existing_users = {u.username: u for u in db.query(User).all()}
        for user_data in DEFAULT_USERS:
            role_codes = user_data.pop("role_codes")
            password = user_data.pop("password")
            if user_data["username"] not in existing_users:
                user = User(**user_data)
                user.hashed_password = get_password_hash(password)
                user.is_active = True
                for code in role_codes:
                    if code in all_roles:
                        user.roles.append(all_roles[code])
                db.add(user)
                logger.info(f"创建用户: {user_data['username']} - {user_data['real_name']}")
            else:
                existing = existing_users[user_data["username"]]
                existing.real_name = user_data["real_name"]
                existing.email = user_data["email"]
                existing.phone = user_data["phone"]
                existing.employee_id = user_data["employee_id"]
                existing.roles.clear()
                for code in role_codes:
                    if code in all_roles:
                        existing.roles.append(all_roles[code])
                logger.info(f"更新用户: {user_data['username']} - {user_data['real_name']}")
        db.commit()
        logger.info(f"用户初始化完成，共 {len(DEFAULT_USERS)} 个用户")
        
        logger.info("数据库初始化完成！")
        logger.info("默认账号信息:")
        for user_data in DEFAULT_USERS:
            logger.info(f"  用户名: {user_data['username']}, 密码: {user_data['password']}, 角色: {user_data['role_codes']}")
            
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
