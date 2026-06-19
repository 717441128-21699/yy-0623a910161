from datetime import date, timedelta
from app.database import Database
from app.models import Patient, Visit

Database.init()

sample_patients = [
    {'name': '张小明', 'phone': '13800138001', 'age': 25, 'gender': '男', 'treatment_plan': '正畸治疗'},
    {'name': '李芳芳', 'phone': '13800138002', 'age': 32, 'gender': '女', 'treatment_plan': '种植牙'},
    {'name': '王建国', 'phone': '13800138003', 'age': 45, 'gender': '男', 'treatment_plan': '牙齿矫正'},
]

today = date.today()
stages = ['initial', 'month1', 'month3']

for patient_data in sample_patients:
    patient = Patient(**patient_data)
    patient_id = Database.add_patient(patient)

    for i, stage in enumerate(stages):
        visit_date = today - timedelta(days=(len(stages) - 1 - i) * 30)
        visit = Visit(
            patient_id=patient_id,
            visit_date=visit_date,
            stage_code=stage,
            notes=f'{stage}复诊'
        )
        Database.add_visit(visit)

print('示例数据初始化完成！')
print(f'已添加 {len(sample_patients)} 位患者，每位患者有 {len(stages)} 次复诊记录')
