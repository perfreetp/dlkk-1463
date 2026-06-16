import sys
import random
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import (
    Hospital, Department, Equipment, Room, Technician, Doctor,
    Examination, ImageQuality, BIRADSReport
)
from app.core.logger import logger

HOSPITALS = [
    {"name": "集团总院", "code": "HOSP001", "address": "北京市朝阳区医疗大道1号", "phone": "010-12345678", "level": "三级甲等"},
    {"name": "第一分院", "code": "HOSP002", "address": "北京市海淀区健康路2号", "phone": "010-23456789", "level": "三级乙等"},
    {"name": "第二分院", "code": "HOSP003", "address": "北京市西城区杏林街3号", "phone": "010-34567890", "level": "三级甲等"},
]

DEPARTMENTS = [
    {"name": "放射科", "code": "RAD001"},
    {"name": "影像诊断科", "code": "RAD002"},
    {"name": "医学影像中心", "code": "RAD003"},
]

EQUIPMENTS = [
    {"brand": "GE", "model": "Senographe Pristina", "type": "DR", "manufacture_date": "2022-01-15"},
    {"brand": "Siemens", "model": "Mammomat Inspiration", "type": "DR", "manufacture_date": "2021-06-20"},
    {"brand": "Hologic", "model": "Selenia Dimensions", "type": "DR", "manufacture_date": "2023-03-10"},
    {"brand": "GE", "model": "Senographe Crystal", "type": "DR", "manufacture_date": "2020-11-05"},
    {"brand": "Siemens", "model": "Mammomat Fusion", "type": "DR", "manufacture_date": "2022-08-18"},
]

ROOMS = [
    {"name": "DR机房1", "code": "RM001"},
    {"name": "DR机房2", "code": "RM002"},
    {"name": "乳腺DR机房", "code": "RM003"},
]

TECHNICIANS = [
    {"name": "王技师", "employee_id": "TECH001", "title": "主管技师", "phone": "13800138101"},
    {"name": "刘技师", "employee_id": "TECH002", "title": "技师", "phone": "13800138102"},
    {"name": "陈技师", "employee_id": "TECH003", "title": "副主任技师", "phone": "13800138103"},
    {"name": "赵技师", "employee_id": "TECH004", "title": "技师", "phone": "13800138104"},
    {"name": "孙技师", "employee_id": "TECH005", "title": "主管技师", "phone": "13800138105"},
]

DOCTORS = [
    {"name": "李医生", "employee_id": "DOC001", "title": "主任医师", "phone": "13800138201"},
    {"name": "张医生", "employee_id": "DOC002", "title": "副主任医师", "phone": "13800138202"},
    {"name": "周医生", "employee_id": "DOC003", "title": "主治医师", "phone": "13800138203"},
    {"name": "吴医生", "employee_id": "DOC004", "title": "主任医师", "phone": "13800138204"},
    {"name": "郑医生", "employee_id": "DOC005", "title": "副主任医师", "phone": "13800138205"},
]

VIEWS = ["CC位+MLO位", "CC位", "MLO位", "CC位+MLO位+XCCL位", "CC位+MLO位+ML位"]
LATERALITIES = ["左侧", "右侧", "双侧"]
BIRADS_CLASSIFICATIONS = ["1类", "2类", "3类", "4A类", "4B类", "4C类", "5类", "6类", "0类"]
BREAST_DENSITIES = ["c型(不均匀致密)", "b型(散在纤维腺体)", "d型(极度致密)", "a型(脂肪型)"]
FINDINGS = [
    "双侧乳腺呈不均匀致密型，未见明确肿块及钙化灶，皮肤乳头未见异常。",
    "左乳外上象限见一簇泥沙样钙化，范围约1.5cm，形态不规则，建议活检。",
    "右乳内下象限见一不规则形肿块，大小约2.3×1.8cm，边界不清，可见毛刺征。",
    "双侧乳腺纤维囊性改变，左乳见多发小圆形钙化，考虑良性。",
    "右乳上方见一卵圆形肿块，边界清晰，大小约1.2×0.9cm，考虑纤维腺瘤。",
    "左乳乳晕后区见结构扭曲，未见明确肿块，建议进一步检查。",
    "双侧乳腺腺体密度不均，未见明确异常征象。",
    "右乳外下象限见细小多形性钙化，呈段样分布，高度可疑恶性。",
]

PATIENT_NAMES = ["张某某", "李某某", "王某某", "刘某某", "陈某某", "杨某某", "赵某某", "黄某某", "周某某", "吴某某"]


def seed_test_data():
    db = SessionLocal()
    try:
        logger.info("开始生成测试数据...")
        
        hospitals = []
        for h_data in HOSPITALS:
            existing = db.query(Hospital).filter_by(code=h_data["code"]).first()
            if not existing:
                hospital = Hospital(**h_data, is_active=True)
                db.add(hospital)
                hospitals.append(hospital)
                logger.info(f"创建院区: {h_data['name']}")
            else:
                hospitals.append(existing)
        db.commit()
        
        departments = []
        for i, d_data in enumerate(DEPARTMENTS):
            hospital = hospitals[i % len(hospitals)]
            existing = db.query(Department).filter_by(code=d_data["code"], hospital_id=hospital.id).first()
            if not existing:
                dept = Department(**d_data, hospital_id=hospital.id, is_active=True)
                db.add(dept)
                departments.append(dept)
                logger.info(f"创建科室: {d_data['name']} - {hospital.name}")
            else:
                departments.append(existing)
        db.commit()
        
        equipments = []
        for i, e_data in enumerate(EQUIPMENTS):
            hospital = hospitals[i % len(hospitals)]
            dept = departments[i % len(departments)]
            existing = db.query(Equipment).filter_by(model=e_data["model"], hospital_id=hospital.id).first()
            if not existing:
                equip = Equipment(**e_data, hospital_id=hospital.id, department_id=dept.id, is_active=True, serial_number=f"SN{i+1:06d}")
                db.add(equip)
                equipments.append(equip)
                logger.info(f"创建设备: {e_data['brand']} {e_data['model']}")
            else:
                equipments.append(existing)
        db.commit()
        
        rooms = []
        for i, r_data in enumerate(ROOMS):
            hospital = hospitals[i % len(hospitals)]
            dept = departments[i % len(departments)]
            equip = equipments[i % len(equipments)]
            existing = db.query(Room).filter_by(code=r_data["code"], hospital_id=hospital.id).first()
            if not existing:
                room = Room(**r_data, hospital_id=hospital.id, department_id=dept.id, equipment_id=equip.id, is_active=True)
                db.add(room)
                rooms.append(room)
                logger.info(f"创建机房: {r_data['name']}")
            else:
                rooms.append(existing)
        db.commit()
        
        technicians = []
        for i, t_data in enumerate(TECHNICIANS):
            hospital = hospitals[i % len(hospitals)]
            dept = departments[i % len(departments)]
            existing = db.query(Technician).filter_by(employee_id=t_data["employee_id"]).first()
            if not existing:
                tech = Technician(**t_data, hospital_id=hospital.id, department_id=dept.id, is_active=True)
                db.add(tech)
                technicians.append(tech)
                logger.info(f"创建技师: {t_data['name']}")
            else:
                technicians.append(existing)
        db.commit()
        
        doctors = []
        for i, d_data in enumerate(DOCTORS):
            hospital = hospitals[i % len(hospitals)]
            dept = departments[i % len(departments)]
            existing = db.query(Doctor).filter_by(employee_id=d_data["employee_id"]).first()
            if not existing:
                doc = Doctor(**d_data, hospital_id=hospital.id, department_id=dept.id, is_active=True)
                db.add(doc)
                doctors.append(doc)
                logger.info(f"创建医生: {d_data['name']}")
            else:
                doctors.append(existing)
        db.commit()
        
        exam_count = db.query(Examination).count()
        if exam_count < 100:
            logger.info(f"开始生成检查数据，目标200条...")
            base_date = datetime.now() - timedelta(days=30)
            
            for i in range(200):
                exam_date = base_date + timedelta(days=random.randint(0, 30), hours=random.randint(8, 18))
                hospital = random.choice(hospitals)
                dept = random.choice([d for d in departments if d.hospital_id == hospital.id])
                equip = random.choice([e for e in equipments if e.hospital_id == hospital.id])
                room = random.choice([r for r in rooms if r.hospital_id == hospital.id])
                tech = random.choice([t for t in technicians if t.hospital_id == hospital.id])
                doc = random.choice([d for d in doctors if d.hospital_id == hospital.id])
                
                patient_age = random.randint(35, 75)
                laterality = random.choice(LATERALITIES)
                views = random.choice(VIEWS)
                birads = random.choice(BIRADS_CLASSIFICATIONS)
                density = random.choice(BREAST_DENSITIES)
                findings = random.choice(FINDINGS)
                
                exam = Examination(
                    accession_number=f"ACC{exam_date.strftime('%Y%m%d')}{i+1:04d}",
                    patient_name=random.choice(PATIENT_NAMES),
                    patient_id=f"P{random.randint(10000, 99999)}",
                    patient_gender="女",
                    patient_age=patient_age,
                    patient_phone=f"138{random.randint(10000000, 99999999)}",
                    patient_id_card=f"11010119{random.randint(50, 90):02d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}{random.randint(1000, 9999)}",
                    examination_date=exam_date,
                    laterality=laterality,
                    views=views,
                    hospital_id=hospital.id,
                    department_id=dept.id,
                    equipment_id=equip.id,
                    room_id=room.id,
                    technician_id=tech.id,
                    doctor_id=doc.id,
                    status="completed",
                )
                db.add(exam)
                db.flush()
                
                iq = ImageQuality(
                    examination_id=exam.id,
                    position_accuracy=random.choice(["complete", "partial", "incomplete"]),
                    image_quality_score=random.randint(60, 100),
                    compression_force=round(random.uniform(80, 140), 1),
                    exposure_dose=round(random.uniform(1.5, 4.5), 2),
                    artifacts_present=random.choice([True, False]),
                    artifacts_description=random.choice(["运动伪影", "异物伪影", None]),
                )
                db.add(iq)
                
                br = BIRADSReport(
                    examination_id=exam.id,
                    breast_density=density,
                    birads_classification=birads,
                    findings_description=findings,
                    assessment_recommendation=("建议随访" if birads in ["1类", "2类", "3类"] else "建议活检"),
                    report_date=exam_date + timedelta(hours=random.randint(1, 24)),
                )
                db.add(br)
                
                if (i + 1) % 50 == 0:
                    db.commit()
                    logger.info(f"已生成 {i + 1} 条检查数据")
            
            db.commit()
            logger.info("检查数据生成完成，共200条")
        else:
            logger.info(f"检查数据已存在 {exam_count} 条，跳过生成")
        
        logger.info("测试数据生成完成！")
        logger.info(f"院区: {len(hospitals)} 家")
        logger.info(f"科室: {len(departments)} 个")
        logger.info(f"设备: {len(equipments)} 台")
        logger.info(f"机房: {len(rooms)} 个")
        logger.info(f"技师: {len(technicians)} 人")
        logger.info(f"医生: {len(doctors)} 人")
        
    except Exception as e:
        logger.error(f"测试数据生成失败: {str(e)}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_test_data()
