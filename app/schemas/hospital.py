from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict, EmailStr


class HospitalBase(BaseModel):
    code: str = Field(..., max_length=50, description="院区编码")
    name: str = Field(..., max_length=200, description="院区名称")
    short_name: Optional[str] = Field(None, max_length=100, description="简称")
    address: Optional[str] = Field(None, max_length=500, description="地址")
    level: Optional[str] = Field(None, max_length=50, description="医院等级")
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class HospitalCreate(HospitalBase):
    pass


class HospitalUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=200)
    short_name: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = Field(None, max_length=500)
    level: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class HospitalResponse(HospitalBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    code: str = Field(..., max_length=50, description="科室编码")
    name: str = Field(..., max_length=200, description="科室名称")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentResponse(DepartmentBase):
    id: int
    hospital_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EquipmentBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    room_id: Optional[int] = Field(None, description="机房ID")
    code: str = Field(..., max_length=100, description="设备编码")
    name: str = Field(..., max_length=200, description="设备名称")
    brand: str = Field(..., max_length=100, description="设备品牌")
    model: Optional[str] = Field(None, max_length=100, description="型号")
    serial_number: Optional[str] = Field(None, max_length=100, description="序列号")
    install_date: Optional[date] = Field(None, description="安装日期")
    last_maintenance_date: Optional[date] = Field(None, description="上次维护日期")
    next_maintenance_date: Optional[date] = Field(None, description="下次维护日期")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    room_id: Optional[int] = None
    code: Optional[str] = Field(None, max_length=100)
    name: Optional[str] = Field(None, max_length=200)
    brand: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    serial_number: Optional[str] = Field(None, max_length=100)
    install_date: Optional[date] = None
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class EquipmentResponse(EquipmentBase):
    id: int
    hospital_name: Optional[str] = None
    room_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    code: str = Field(..., max_length=50, description="机房编码")
    name: str = Field(..., max_length=100, description="机房名称")
    floor: Optional[str] = Field(None, max_length=20, description="楼层")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=100)
    floor: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class RoomResponse(RoomBase):
    id: int
    hospital_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TechnicianBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    code: str = Field(..., max_length=50, description="技师编码")
    name: str = Field(..., max_length=100, description="姓名")
    gender: Optional[str] = Field(None, max_length=10, description="性别")
    title: Optional[str] = Field(None, max_length=50, description="职称")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    hire_date: Optional[date] = Field(None, description="入职日期")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class TechnicianCreate(TechnicianBase):
    pass


class TechnicianUpdate(BaseModel):
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    title: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    hire_date: Optional[date] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class TechnicianResponse(TechnicianBase):
    id: int
    hospital_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DoctorBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    department_id: Optional[int] = Field(None, description="科室ID")
    code: str = Field(..., max_length=50, description="医生编码")
    name: str = Field(..., max_length=100, description="姓名")
    gender: Optional[str] = Field(None, max_length=10, description="性别")
    title: Optional[str] = Field(None, max_length=50, description="职称")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    specialty: Optional[str] = Field(None, max_length=100, description="专长")
    description: Optional[str] = Field(None, description="描述")
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(BaseModel):
    department_id: Optional[int] = None
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=10)
    title: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    specialty: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class DoctorResponse(DoctorBase):
    id: int
    hospital_name: Optional[str] = None
    department_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
