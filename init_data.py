import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibration_system.settings')
django.setup()

from api.database import (
    users_table, instrument_categories_table,
    experiment_regions_table, storage_locations_table,
    responsible_persons_table, calibration_rules_table,
    instruments_table, calibration_records_table,
    calibration_appointments_table, generate_id, now_str
)
from api.auth_backend import hash_password


def init_default_data():
    if users_table.all():
        print('数据已存在，跳过初始化')
        return

    print('开始初始化默认数据...')

    users = [
        {'username': 'admin', 'password': hash_password('admin123'), 'role': 'admin',
         'name': '系统管理员', 'department': '信息中心', 'phone': '13800138000', 'email': 'admin@school.edu.cn'},
        {'username': 'exp01', 'password': hash_password('exp123'), 'role': 'experimenter',
         'name': '张实验员', 'department': '物理学院', 'phone': '13800138001', 'email': 'exp01@school.edu.cn'},
        {'username': 'exp02', 'password': hash_password('exp123'), 'role': 'experimenter',
         'name': '李实验员', 'department': '化学学院', 'phone': '13800138002', 'email': 'exp02@school.edu.cn'},
        {'username': 'audit01', 'password': hash_password('audit123'), 'role': 'auditor',
         'name': '王审核', 'department': '设备管理处', 'phone': '13800138003', 'email': 'audit01@school.edu.cn'},
        {'username': 'cali01', 'password': hash_password('cali123'), 'role': 'calibrator',
         'name': '赵校准', 'department': '计量中心', 'phone': '13800138004', 'email': 'cali01@school.edu.cn'},
        {'username': 'cali02', 'password': hash_password('cali123'), 'role': 'calibrator',
         'name': '钱校准', 'department': '计量中心', 'phone': '13800138005', 'email': 'cali02@school.edu.cn'},
    ]
    for user in users:
        uid = generate_id(users_table)
        users_table.insert({'id': uid, **user, 'created_at': now_str()})
    print(f'  - 创建 {len(users)} 个用户')

    categories = [
        {'name': '天平', 'code': 'BAL', 'description': '各类分析天平、电子天平'},
        {'name': '温度计', 'code': 'THM', 'description': '玻璃温度计、铂电阻温度计'},
        {'name': '压力表', 'code': 'PRS', 'description': '精密压力表、数字压力表'},
        {'name': '分光光度计', 'code': 'SPT', 'description': '紫外/可见分光光度计'},
        {'name': '酸度计', 'code': 'PHM', 'description': '实验室pH计、离子计'},
    ]
    for cat in categories:
        cid = generate_id(instrument_categories_table)
        instrument_categories_table.insert({'id': cid, **cat, 'created_at': now_str()})
    print(f'  - 创建 {len(categories)} 个仪器类别')

    regions = [
        {'name': '物理实验中心', 'code': 'PHY', 'department': '物理学院'},
        {'name': '化学实验中心', 'code': 'CHEM', 'department': '化学学院'},
        {'name': '生物实验中心', 'code': 'BIO', 'department': '生命科学学院'},
        {'name': '材料实验室', 'code': 'MAT', 'department': '材料科学与工程学院'},
        {'name': '环境监测站', 'code': 'ENV', 'department': '环境科学与工程学院'},
    ]
    for reg in regions:
        rid = generate_id(experiment_regions_table)
        experiment_regions_table.insert({'id': rid, **reg, 'created_at': now_str()})
    print(f'  - 创建 {len(regions)} 个实验区域')

    locations = [
        {'name': 'A栋101室', 'code': 'A101', 'building': '实验楼A栋', 'floor': '1F', 'room': '101'},
        {'name': 'A栋201室', 'code': 'A201', 'building': '实验楼A栋', 'floor': '2F', 'room': '201'},
        {'name': 'B栋101室', 'code': 'B101', 'building': '实验楼B栋', 'floor': '1F', 'room': '101'},
        {'name': 'B栋201室', 'code': 'B201', 'building': '实验楼B栋', 'floor': '2F', 'room': '201'},
        {'name': 'C栋301室', 'code': 'C301', 'building': '实验楼C栋', 'floor': '3F', 'room': '301'},
    ]
    for loc in locations:
        lid = generate_id(storage_locations_table)
        storage_locations_table.insert({'id': lid, **loc, 'created_at': now_str()})
    print(f'  - 创建 {len(locations)} 个存放位置')

    persons = [
        {'name': '陈主任', 'department': '物理学院', 'phone': '13900139001', 'email': 'chen@school.edu.cn'},
        {'name': '刘教授', 'department': '化学学院', 'phone': '13900139002', 'email': 'liu@school.edu.cn'},
        {'name': '周老师', 'department': '生命科学学院', 'phone': '13900139003', 'email': 'zhou@school.edu.cn'},
        {'name': '吴老师', 'department': '材料学院', 'phone': '13900139004', 'email': 'wu@school.edu.cn'},
    ]
    for person in persons:
        pid = generate_id(responsible_persons_table)
        responsible_persons_table.insert({'id': pid, **person, 'created_at': now_str()})
    print(f'  - 创建 {len(persons)} 个责任人')

    rules = [
        {'name': '分析天平校准规则', 'instrument_category_id': 1, 'cycle_days': 180,
         'tolerance': 0.0001, 'standard_value': 100.0, 'unit': 'g'},
        {'name': '温度计校准规则', 'instrument_category_id': 2, 'cycle_days': 365,
         'tolerance': 0.1, 'standard_value': 25.0, 'unit': '℃'},
        {'name': '压力表校准规则', 'instrument_category_id': 3, 'cycle_days': 180,
         'tolerance': 0.01, 'standard_value': 1.0, 'unit': 'MPa'},
        {'name': '分光光度计校准规则', 'instrument_category_id': 4, 'cycle_days': 365,
         'tolerance': 0.005, 'standard_value': 0.5, 'unit': 'Abs'},
        {'name': 'pH计校准规则', 'instrument_category_id': 5, 'cycle_days': 90,
         'tolerance': 0.02, 'standard_value': 7.0, 'unit': 'pH'},
    ]
    for rule in rules:
        rid = generate_id(calibration_rules_table)
        calibration_rules_table.insert({'id': rid, **rule, 'created_at': now_str()})
    print(f'  - 创建 {len(rules)} 个校准规则')

    today = datetime.now()
    instruments = [
        {'serial_number': 'BAL-2024-001', 'name': '梅特勒分析天平', 'category_id': 1,
         'model': 'ME204E', 'manufacturer': '梅特勒托利多',
         'purchase_date': (today - timedelta(days=180 + 45)).strftime('%Y-%m-%d'),
         'region_id': 1, 'location_id': 1, 'responsible_person_id': 1, 'rule_id': 1,
         'status': 'active'},
        {'serial_number': 'BAL-2024-002', 'name': '赛多利斯电子天平', 'category_id': 1,
         'model': 'BSA224S', 'manufacturer': '赛多利斯',
         'purchase_date': (today - timedelta(days=180 + 10)).strftime('%Y-%m-%d'),
         'region_id': 2, 'location_id': 3, 'responsible_person_id': 2, 'rule_id': 1,
         'status': 'active'},
        {'serial_number': 'THM-2024-001', 'name': '精密玻璃温度计', 'category_id': 2,
         'model': 'WNG-01', 'manufacturer': '上海精密仪器厂',
         'purchase_date': (today - timedelta(days=365 - 15)).strftime('%Y-%m-%d'),
         'region_id': 1, 'location_id': 1, 'responsible_person_id': 1, 'rule_id': 2,
         'status': 'active'},
        {'serial_number': 'PRS-2024-001', 'name': '数字压力表', 'category_id': 3,
         'model': 'DPG-100', 'manufacturer': '福禄克',
         'purchase_date': (today - timedelta(days=180 - 20)).strftime('%Y-%m-%d'),
         'region_id': 4, 'location_id': 5, 'responsible_person_id': 4, 'rule_id': 3,
         'status': 'active'},
        {'serial_number': 'SPT-2024-001', 'name': '紫外可见分光光度计', 'category_id': 4,
         'model': 'UV-1800', 'manufacturer': '岛津',
         'purchase_date': (today - timedelta(days=60)).strftime('%Y-%m-%d'),
         'region_id': 2, 'location_id': 4, 'responsible_person_id': 2, 'rule_id': 4,
         'status': 'active'},
        {'serial_number': 'PHM-2024-001', 'name': '实验室pH计', 'category_id': 5,
         'model': 'FE28', 'manufacturer': '梅特勒托利多',
         'purchase_date': (today - timedelta(days=90 + 90)).strftime('%Y-%m-%d'),
         'region_id': 5, 'location_id': 5, 'responsible_person_id': 3, 'rule_id': 5,
         'status': 'active'},
        {'serial_number': 'BAL-2024-003', 'name': '奥豪斯分析天平', 'category_id': 1,
         'model': 'AX224', 'manufacturer': '奥豪斯',
         'purchase_date': (today - timedelta(days=180 + 60)).strftime('%Y-%m-%d'),
         'region_id': 3, 'location_id': 2, 'responsible_person_id': 3, 'rule_id': 1,
         'status': 'active'},
        {'serial_number': 'THM-2024-002', 'name': '铂电阻温度计', 'category_id': 2,
         'model': 'PT100', 'manufacturer': '德国JUMO',
         'purchase_date': (today - timedelta(days=365 - 5)).strftime('%Y-%m-%d'),
         'region_id': 4, 'location_id': 5, 'responsible_person_id': 4, 'rule_id': 2,
         'status': 'active'},
        {'serial_number': 'PHM-2024-002', 'name': '工业pH计', 'category_id': 5,
         'model': 'PH700', 'manufacturer': '哈希',
         'purchase_date': (today - timedelta(days=90 + 30)).strftime('%Y-%m-%d'),
         'region_id': 2, 'location_id': 3, 'responsible_person_id': 2, 'rule_id': 5,
         'status': 'active'},
    ]
    for inst in instruments:
        iid = generate_id(instruments_table)
        instruments_table.insert({'id': iid, **inst, 'created_at': now_str()})
    print(f'  - 创建 {len(instruments)} 台仪器')

    print('初始化完成！')
    print('\n默认账号：')
    print('  管理员: admin / admin123')
    print('  实验员: exp01 / exp123, exp02 / exp123')
    print('  审核人: audit01 / audit123')
    print('  校准员: cali01 / cali123, cali02 / cali123')


if __name__ == '__main__':
    init_default_data()
