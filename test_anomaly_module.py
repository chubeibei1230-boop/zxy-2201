import os
import sys
import django
from pathlib import Path
from datetime import datetime, timedelta
import json

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'calibration_system.settings')
django.setup()

from django.test import Client
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User

client = Client()

def print_separator(title=''):
    print('\n' + '='*60)
    if title:
        print(f'  {title}')
        print('='*60)

def print_response(response, show_body=True, max_len=1000):
    print(f'  Status: {response.status_code}')
    if show_body and response.content:
        try:
            data = json.loads(response.content)
            content_str = json.dumps(data, ensure_ascii=False, indent=2)
            if len(content_str) > max_len:
                content_str = content_str[:max_len] + '...'
            print(f'  Response: {content_str}')
        except:
            print(f'  Response: {response.content[:300]}')

def get_auth_token(username):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User(username=username)
        user.set_unusable_password()
        user.is_active = True
        user.save()
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)

def test_with_auth(method, url, token, data=None):
    headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
    if method == 'GET':
        return client.get(url, data=data, **headers)
    elif method == 'POST':
        return client.post(url, data=data, content_type='application/json', **headers)
    elif method == 'PUT':
        return client.put(url, data=data, content_type='application/json', **headers)
    elif method == 'DELETE':
        return client.delete(url, **headers)

def test_anomaly_list():
    print_separator('测试异常任务列表')
    admin_token = get_auth_token('admin')
    
    print('  获取所有异常任务:')
    response = test_with_auth('GET', '/api/anomalies/', admin_token)
    print_response(response)
    assert response.status_code == 200, '获取异常任务列表失败'
    anomalies = json.loads(response.content)
    assert isinstance(anomalies, list), '返回应为列表'
    print(f'     异常任务数量: {len(anomalies)}')
    
    for a in anomalies:
        assert 'anomaly_no' in a
        assert 'anomaly_type_label' in a
        assert 'anomaly_level_label' in a
        assert 'status_label' in a
        assert 'instrument' in a
        assert 'appointment' in a
    
    print('\n  按状态筛选 (registered):')
    response = test_with_auth('GET', '/api/anomalies/?status=registered', admin_token)
    assert response.status_code == 200
    registered = json.loads(response.content)
    print(f'     已登记异常数量: {len(registered)}')
    for a in registered:
        assert a.get('status') == 'registered'
    
    print('\n  按异常等级筛选 (minor):')
    response = test_with_auth('GET', '/api/anomalies/?anomaly_level=minor', admin_token)
    assert response.status_code == 200
    minor = json.loads(response.content)
    print(f'     轻微异常数量: {len(minor)}')
    
    print('\n  按异常类型筛选 (deviation):')
    response = test_with_auth('GET', '/api/anomalies/?anomaly_type=deviation', admin_token)
    assert response.status_code == 200
    deviation = json.loads(response.content)
    print(f'     校准偏差异常数量: {len(deviation)}')
    
    print('\n  ✓ 异常任务列表测试通过！')
    return anomalies[0]['id'] if anomalies else None

def test_anomaly_detail():
    print_separator('测试异常任务详情')
    admin_token = get_auth_token('admin')
    
    response = test_with_auth('GET', '/api/anomalies/', admin_token)
    anomalies = json.loads(response.content)
    assert len(anomalies) > 0, '异常任务列表不应为空'
    anomaly_id = anomalies[0]['id']
    
    print(f'  获取异常任务详情 (id={anomaly_id}):')
    response = test_with_auth('GET', f'/api/anomalies/{anomaly_id}/', admin_token)
    print_response(response)
    assert response.status_code == 200, '获取异常任务详情失败'
    detail = json.loads(response.content)
    
    assert 'anomaly_type_label' in detail
    assert 'anomaly_level_label' in detail
    assert 'status_label' in detail
    assert 'appointment' in detail
    assert 'instrument' in detail
    assert 'category' in detail
    assert 'region' in detail
    assert 'responsible_person' in detail
    assert 'calibration_record' in detail
    assert 'process_records' in detail
    assert isinstance(detail['process_records'], list)
    assert len(detail['process_records']) > 0
    
    print(f'     异常编号: {detail.get("anomaly_no")}')
    print(f'     异常类型: {detail.get("anomaly_type_label")}')
    print(f'     异常等级: {detail.get("anomaly_level_label")}')
    print(f'     当前状态: {detail.get("status_label")}')
    print(f'     处置记录数: {len(detail["process_records"])}')
    
    print('\n  ✓ 异常任务详情测试通过！')
    return anomaly_id

def test_anomaly_workflow():
    print_separator('测试异常处置完整流程')
    
    exp_token = get_auth_token('exp02')
    audit_token = get_auth_token('audit01')
    admin_token = get_auth_token('admin')
    cali_token = get_auth_token('cali01')
    
    response = test_with_auth('GET', '/api/anomalies/?status=registered', admin_token)
    registered = json.loads(response.content)
    assert len(registered) > 0, '应有已登记的异常任务'
    anomaly_id = registered[0]['id']
    print(f'  选择异常任务 id={anomaly_id}')
    
    print('\n  1. 实验员进行原因分析:')
    response = test_with_auth('POST', '/api/anomalies/analysis/', exp_token, {
        'anomaly_task_id': anomaly_id,
        'cause_analysis': '经过仔细分析，偏差主要由于以下原因：\n1. 环境温度波动较大\n2. 仪器使用频率高，需要定期维护\n3. 标准砝码需要重新校准',
        'root_cause': '环境温度波动和仪器老化'
    })
    print_response(response)
    assert response.status_code == 200, '原因分析提交失败'
    result = json.loads(response.content)
    assert result['data']['status'] == 'analyzing', '状态应为分析中'
    print('     ✓ 原因分析提交成功')
    
    print('\n  2. 实验员制定整改措施:')
    deadline = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    response = test_with_auth('POST', '/api/anomalies/rectification/', exp_token, {
        'anomaly_task_id': anomaly_id,
        'rectification_measures': '1. 安装恒温装置，稳定环境温度\n2. 安排仪器维护保养计划\n3. 送修标准砝码进行校准',
        'responsible_person': '李实验员',
        'completion_deadline': deadline
    })
    print_response(response)
    assert response.status_code == 200, '整改措施提交失败'
    result = json.loads(response.content)
    assert result['data']['status'] == 'rectifying', '状态应为整改中'
    print('     ✓ 整改措施提交成功')
    
    print('\n  3. 审核人进行复核:')
    response = test_with_auth('POST', '/api/anomalies/review/', audit_token, {
        'anomaly_task_id': anomaly_id,
        'review_opinion': '整改措施合理可行，同意通过复核。建议增加日常巡检频率。',
        'review_result': 'pass'
    })
    print_response(response)
    assert response.status_code == 200, '复核提交失败'
    result = json.loads(response.content)
    assert result['data']['status'] == 'reviewing', '状态应为复核中/待结案'
    print('     ✓ 复核通过')
    
    print('\n  4. 管理员进行结案:')
    response = test_with_auth('POST', '/api/anomalies/close/', admin_token, {
        'anomaly_task_id': anomaly_id,
        'conclusion': '异常已妥善处理，整改措施落实到位，仪器已恢复正常使用状态。',
        'closing_remark': '建议每月进行一次仪器状态检查'
    })
    print_response(response)
    assert response.status_code == 200, '结案失败'
    result = json.loads(response.content)
    assert result['data']['status'] == 'closed', '状态应为已结案'
    assert result['data']['closed_at'] is not None, '应有结案时间'
    print('     ✓ 异常已结案')
    
    print('\n  5. 验证处置链路完整:')
    response = test_with_auth('GET', f'/api/anomalies/{anomaly_id}/', admin_token)
    detail = json.loads(response.content)
    process_records = detail['process_records']
    print(f'     处置记录数: {len(process_records)}')
    steps = [r['step'] for r in process_records]
    print(f'     处置步骤: {steps}')
    
    assert 'register' in steps, '应有登记步骤'
    assert 'analysis' in steps, '应有分析步骤'
    assert 'rectification' in steps, '应有整改步骤'
    assert 'review' in steps, '应有复核步骤'
    assert 'close' in steps, '应有结案步骤'
    
    print('\n  ✓ 异常处置完整流程测试通过！')

def test_anomaly_dashboard():
    print_separator('测试异常统计汇总看板')
    admin_token = get_auth_token('admin')
    
    print('  获取异常看板数据:')
    response = test_with_auth('GET', '/api/anomalies/dashboard/', admin_token)
    print_response(response)
    assert response.status_code == 200, '获取看板数据失败'
    dashboard = json.loads(response.content)
    
    assert 'summary' in dashboard, '应包含汇总数据'
    summary = dashboard['summary']
    print(f'     汇总: {json.dumps(summary, ensure_ascii=False)}')
    assert 'total' in summary
    assert 'pending' in summary
    assert 'closed' in summary
    assert 'registered' in summary
    assert 'analyzing' in summary
    assert 'rectifying' in summary
    assert 'reviewing' in summary
    
    assert 'by_type' in dashboard, '应包含按类型统计'
    by_type = dashboard['by_type']
    print(f'     按类型: {list(by_type.keys())}')
    
    assert 'by_level' in dashboard, '应包含按等级统计'
    by_level = dashboard['by_level']
    print(f'     按等级: {list(by_level.keys())}')
    
    assert 'by_region' in dashboard, '应包含按区域统计'
    by_region = dashboard['by_region']
    print(f'     按区域: {list(by_region.keys())}')
    
    assert 'by_category' in dashboard, '应包含按类别统计'
    by_category = dashboard['by_category']
    print(f'     按类别: {list(by_category.keys())}')
    
    assert 'generated_at' in dashboard, '应包含生成时间'
    
    print('\n  ✓ 异常统计汇总看板测试通过！')

def test_auto_create_anomaly():
    print_separator('测试自动创建异常任务')
    
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print('  1. 创建校准预约:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 4,
        'applicant': '张实验员',
        'department': '物理学院',
        'purpose': '测试自动创建异常任务',
        'expected_date': tomorrow
    })
    assert response.status_code == 201
    apt_data = json.loads(response.content)
    apt_id = apt_data['id']
    print(f'     预约ID: {apt_id}')
    
    print('  2. 创建前置检查:')
    response = test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id,
        'experimenter': '张实验员',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [
            {'name': '外观检查', 'result': True, 'remark': ''},
            {'name': '电源检查', 'result': True, 'remark': ''}
        ],
        'overall_result': True,
        'remark': '检查通过'
    })
    assert response.status_code == 201
    
    print('  3. 提交审核:')
    response = test_with_auth('POST', '/api/appointments/submit/', exp_token, {
        'appointment_id': apt_id
    })
    assert response.status_code == 200
    
    print('  4. 审核通过:')
    response = test_with_auth('POST', '/api/audits/', audit_token, {
        'appointment_id': apt_id,
        'auditor': '王审核',
        'result': 'approved',
        'opinion': '同意校准'
    })
    assert response.status_code == 200
    
    print('  5. 开始校准:')
    response = test_with_auth('POST', '/api/calibrations/start/', cali_token, {
        'appointment_id': apt_id
    })
    assert response.status_code == 200
    
    print('  6. 记录偏差结果（应自动创建异常任务）:')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    response = test_with_auth('POST', '/api/calibrations/record/', cali_token, {
        'appointment_id': apt_id,
        'calibrator': '赵校准',
        'start_date': now,
        'end_date': now,
        'standard_value': 1.0,
        'measured_value': 0.95,
        'deviation_level': 'major',
        'accessory_status': 'damaged',
        'accessory_remark': '压力表接头有磨损',
        'environment_temp': 23.5,
        'environment_humidity': 45.0,
        'calibration_method': '标准表比较法',
        'conclusion': '偏差较大，配件损坏',
        'closing_remark': '需异常处置'
    })
    print_response(response)
    assert response.status_code == 200
    
    print('\n  7. 验证自动创建的异常任务:')
    response = test_with_auth('GET', f'/api/anomalies/?appointment_id={apt_id}', admin_token)
    anomalies = json.loads(response.content)
    print(f'     关联的异常任务数: {len(anomalies)}')
    assert len(anomalies) >= 2, '应至少创建2条异常任务（偏差+配件损坏）'
    
    anomaly_types = [a['anomaly_type'] for a in anomalies]
    print(f'     异常类型: {anomaly_types}')
    assert 'deviation' in anomaly_types, '应有偏差异常'
    assert 'accessory_damaged' in anomaly_types, '应有配件损坏异常'
    
    for a in anomalies:
        print(f'       - {a["anomaly_type_label"]} ({a["anomaly_level_label"]}): {a["title"]}')
    
    print('\n  ✓ 自动创建异常任务测试通过！')
    return apt_id

def test_anomaly_role_permissions():
    print_separator('测试异常处置模块角色权限')
    
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')
    
    print('  异常列表 - 各角色均可访问:')
    for role, token in [('实验员', exp_token), ('审核人', audit_token), ('校准员', cali_token), ('管理员', admin_token)]:
        response = test_with_auth('GET', '/api/anomalies/', token)
        assert response.status_code == 200, f'{role}应能访问异常列表'
    print('     ✓ 所有角色均可访问异常列表')
    
    print('  异常看板 - 仅管理员可访问:')
    response = test_with_auth('GET', '/api/anomalies/dashboard/', exp_token)
    assert response.status_code == 403, '实验员不应访问看板'
    response = test_with_auth('GET', '/api/anomalies/dashboard/', audit_token)
    assert response.status_code == 403, '审核人不应访问看板'
    response = test_with_auth('GET', '/api/anomalies/dashboard/', cali_token)
    assert response.status_code == 403, '校准员不应访问看板'
    response = test_with_auth('GET', '/api/anomalies/dashboard/', admin_token)
    assert response.status_code == 200, '管理员应能访问看板'
    print('     ✓ 仅管理员可访问异常看板')
    
    print('  原因分析 - 实验员和管理员可访问:')
    response = test_with_auth('POST', '/api/anomalies/analysis/', cali_token, {
        'anomaly_task_id': 1,
        'cause_analysis': '测试'
    })
    assert response.status_code == 403, '校准员不应进行原因分析'
    response = test_with_auth('POST', '/api/anomalies/analysis/', audit_token, {
        'anomaly_task_id': 1,
        'cause_analysis': '测试'
    })
    assert response.status_code == 403, '审核人不应进行原因分析'
    print('     ✓ 原因分析权限正确')
    
    print('  复核确认 - 审核人和管理员可访问:')
    response = test_with_auth('POST', '/api/anomalies/review/', exp_token, {
        'anomaly_task_id': 1,
        'review_opinion': '测试',
        'review_result': 'pass'
    })
    assert response.status_code == 403, '实验员不应进行复核'
    response = test_with_auth('POST', '/api/anomalies/review/', cali_token, {
        'anomaly_task_id': 1,
        'review_opinion': '测试',
        'review_result': 'pass'
    })
    assert response.status_code == 403, '校准员不应进行复核'
    print('     ✓ 复核确认权限正确')
    
    print('  结案 - 仅管理员可访问:')
    response = test_with_auth('POST', '/api/anomalies/close/', exp_token, {
        'anomaly_task_id': 1,
        'conclusion': '测试'
    })
    assert response.status_code == 403, '实验员不应结案'
    response = test_with_auth('POST', '/api/anomalies/close/', audit_token, {
        'anomaly_task_id': 1,
        'conclusion': '测试'
    })
    assert response.status_code == 403, '审核人不应结案'
    response = test_with_auth('POST', '/api/anomalies/close/', cali_token, {
        'anomaly_task_id': 1,
        'conclusion': '测试'
    })
    assert response.status_code == 403, '校准员不应结案'
    print('     ✓ 结案权限正确')
    
    print('\n  ✓ 异常处置模块角色权限测试通过！')

def test_anomaly_filter():
    print_separator('测试异常任务筛选查询')
    admin_token = get_auth_token('admin')
    
    print('  按实验区域筛选 (region_id=2):')
    response = test_with_auth('GET', '/api/anomalies/?region_id=2', admin_token)
    assert response.status_code == 200
    region_anomalies = json.loads(response.content)
    print(f'     区域2异常数量: {len(region_anomalies)}')
    for a in region_anomalies:
        assert a.get('region', {}).get('id') == 2 or a.get('instrument', {}).get('region_id') == 2
    
    print('\n  按仪器类别筛选 (category_id=1):')
    response = test_with_auth('GET', '/api/anomalies/?category_id=1', admin_token)
    assert response.status_code == 200
    cat_anomalies = json.loads(response.content)
    print(f'     类别1异常数量: {len(cat_anomalies)}')
    
    print('\n  按责任人筛选 (responsible_person_id=2):')
    response = test_with_auth('GET', '/api/anomalies/?responsible_person_id=2', admin_token)
    assert response.status_code == 200
    person_anomalies = json.loads(response.content)
    print(f'     责任人2异常数量: {len(person_anomalies)}')
    
    print('\n  按仪器筛选 (instrument_id=2):')
    response = test_with_auth('GET', '/api/anomalies/?instrument_id=2', admin_token)
    assert response.status_code == 200
    inst_anomalies = json.loads(response.content)
    print(f'     仪器2异常数量: {len(inst_anomalies)}')
    for a in inst_anomalies:
        assert a.get('instrument_id') == 2
    
    print('\n  ✓ 异常任务筛选查询测试通过！')

def test_bugfix_accessory_deviation_pending():
    print_separator('Bug修复测试1: 配件损坏/缺失时预约也应设为偏差待处理')
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')

    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    print('  1. 创建预约并走完审核流程:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 5, 'applicant': '张实验员', 'department': '化学学院',
        'purpose': '测试配件损坏时预约状态', 'expected_date': tomorrow
    })
    assert response.status_code == 201
    apt_id = json.loads(response.content)['id']

    test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id, 'experimenter': '张实验员',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [{'name': '外观检查', 'result': True, 'remark': ''}],
        'overall_result': True, 'remark': 'ok'
    })
    test_with_auth('POST', '/api/appointments/submit/', exp_token, {'appointment_id': apt_id})
    test_with_auth('POST', '/api/audits/', audit_token, {
        'appointment_id': apt_id, 'auditor': '王审核', 'result': 'approved', 'opinion': 'ok'
    })
    test_with_auth('POST', '/api/calibrations/start/', cali_token, {'appointment_id': apt_id})

    print('  2. 记录校准结果：无偏差但配件损坏:')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    response = test_with_auth('POST', '/api/calibrations/record/', cali_token, {
        'appointment_id': apt_id, 'calibrator': '赵校准',
        'start_date': now, 'end_date': now,
        'standard_value': 1.0, 'measured_value': 1.0,
        'deviation_level': 'none',
        'accessory_status': 'missing',
        'accessory_remark': '电源线缺失',
        'conclusion': '校准值合格但配件缺失',
        'closing_remark': ''
    })
    assert response.status_code == 200
    result = json.loads(response.content)
    print(f'     预约状态: {result["appointment"]["status"]}')
    assert result['appointment']['status'] == 'deviation_pending', '配件缺失时预约状态应为deviation_pending'

    print('  3. 验证已自动创建配件缺失异常:')
    response = test_with_auth('GET', f'/api/anomalies/?appointment_id={apt_id}', admin_token)
    anomalies = json.loads(response.content)
    anomaly_types = [a['anomaly_type'] for a in anomalies]
    print(f'     异常类型: {anomaly_types}')
    assert 'accessory_missing' in anomaly_types, '应自动创建配件缺失异常'

    print('\n  ✓ Bug修复测试1通过：配件损坏/缺失时预约状态为偏差待处理')


def test_bugfix_acceptance_with_open_anomaly():
    print_separator('Bug修复测试2: 未结案异常时禁止验收通过')
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')

    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    print('  1. 创建预约并生成偏差异常（不处置）:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 6, 'applicant': '张实验员', 'department': '生命学院',
        'purpose': '测试未结案异常验收', 'expected_date': tomorrow
    })
    assert response.status_code == 201
    apt_id = json.loads(response.content)['id']

    test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id, 'experimenter': '张实验员',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [{'name': '外观检查', 'result': True, 'remark': ''}],
        'overall_result': True, 'remark': 'ok'
    })
    test_with_auth('POST', '/api/appointments/submit/', exp_token, {'appointment_id': apt_id})
    test_with_auth('POST', '/api/audits/', audit_token, {
        'appointment_id': apt_id, 'auditor': '王审核', 'result': 'approved', 'opinion': 'ok'
    })
    test_with_auth('POST', '/api/calibrations/start/', cali_token, {'appointment_id': apt_id})

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    response = test_with_auth('POST', '/api/calibrations/record/', cali_token, {
        'appointment_id': apt_id, 'calibrator': '赵校准',
        'start_date': now, 'end_date': now,
        'standard_value': 1.0, 'measured_value': 0.8,
        'deviation_level': 'major', 'accessory_status': 'normal',
        'conclusion': '偏差较大', 'closing_remark': ''
    })
    assert response.status_code == 200

    print('  2. 尝试直接验收通过（应被拒绝）:')
    response = test_with_auth('POST', '/api/acceptances/', exp_token, {
        'appointment_id': apt_id, 'acceptor': '张实验员',
        'result': True, 'opinion': '我想直接通过'
    })
    print_response(response)
    assert response.status_code == 400, '存在未结案异常时验收通过应返回400'
    detail = json.loads(response.content).get('detail', '')
    assert '未结案' in detail or '异常' in detail, '错误信息应提示存在未结案异常'

    print('\n  ✓ Bug修复测试2通过：未结案异常时无法验收通过')


def test_bugfix_cross_appointment_validation():
    print_separator('Bug修复测试3: 异常任务只能关联同一预约的校准/验收记录')
    cali_token = get_auth_token('cali01')

    print('  尝试创建关联其他预约校准记录的异常:')
    response = test_with_auth('POST', '/api/anomalies/create/', cali_token, {
        'appointment_id': 1,
        'anomaly_type': 'deviation',
        'anomaly_level': 'minor',
        'title': '测试串单',
        'description': '故意关联其他预约的校准记录',
        'calibration_record_id': 99999
    })
    print_response(response)
    assert response.status_code == 400, '关联不存在的校准记录应报错'
    print('     ✓ 不存在的校准记录已被拒绝')

    print('\n  ✓ Bug修复测试3通过：异常关联记录校验正常')


def test_bugfix_invalid_filter_params():
    print_separator('Bug修复测试4: 非法筛选参数不应导致服务端错误')
    admin_token = get_auth_token('admin')

    test_cases = [
        ('region_id=abc', '非法的区域ID'),
        ('category_id=xyz', '非法的类别ID'),
        ('responsible_person_id=!@#', '非法的责任人ID'),
        ('instrument_id=hello', '非法的仪器ID'),
        ('appointment_id=not_a_number', '非法的预约ID'),
    ]

    for qs, desc in test_cases:
        print(f'  测试 {desc}: {qs}')
        response = test_with_auth('GET', f'/api/anomalies/?{qs}', admin_token)
        assert response.status_code == 200, f'{desc}应返回200而非服务端错误'
        print(f'     ✓ 返回状态码 200')

    print('\n  ✓ Bug修复测试4通过：非法筛选参数不会报错')


def test_bugfix_repeated_acceptance_failure_updates_record():
    print_separator('Bug修复测试5: 重复验收不通过时更新已有异常的验收记录')
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')

    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    print('  1. 创建预约并记录校准结果（无偏差）:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 7, 'applicant': '张实验员', 'department': '材料学院',
        'purpose': '测试重复验收不通过', 'expected_date': tomorrow
    })
    assert response.status_code == 201
    apt_id = json.loads(response.content)['id']

    test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id, 'experimenter': '张实验员',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [{'name': '外观检查', 'result': True, 'remark': ''}],
        'overall_result': True, 'remark': 'ok'
    })
    test_with_auth('POST', '/api/appointments/submit/', exp_token, {'appointment_id': apt_id})
    test_with_auth('POST', '/api/audits/', audit_token, {
        'appointment_id': apt_id, 'auditor': '王审核', 'result': 'approved', 'opinion': 'ok'
    })
    test_with_auth('POST', '/api/calibrations/start/', cali_token, {'appointment_id': apt_id})

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    test_with_auth('POST', '/api/calibrations/record/', cali_token, {
        'appointment_id': apt_id, 'calibrator': '赵校准',
        'start_date': now, 'end_date': now,
        'standard_value': 1.0, 'measured_value': 1.0,
        'deviation_level': 'none', 'accessory_status': 'normal',
        'conclusion': '合格', 'closing_remark': ''
    })

    print('  2. 第一次验收不通过:')
    response = test_with_auth('POST', '/api/acceptances/', exp_token, {
        'appointment_id': apt_id, 'acceptor': '张实验员',
        'result': False, 'opinion': '第一次不通过'
    })
    assert response.status_code == 200

    response = test_with_auth('GET', f'/api/anomalies/?appointment_id={apt_id}&anomaly_type=acceptance_failed', admin_token)
    anomalies = json.loads(response.content)
    assert len(anomalies) == 1, '应只有1条验收不通过异常'
    anomaly_id = anomalies[0]['id']
    first_acc_id = anomalies[0].get('acceptance_record_id')
    print(f'     异常ID={anomaly_id}, 关联验收记录ID={first_acc_id}')

    print('  3. 第二次验收不通过:')
    response = test_with_auth('POST', '/api/acceptances/', exp_token, {
        'appointment_id': apt_id, 'acceptor': '张实验员',
        'result': False, 'opinion': '第二次不通过，再次检查'
    })
    assert response.status_code == 200

    print('  4. 验证异常数量仍为1，且验收记录已更新:')
    response = test_with_auth('GET', f'/api/anomalies/?appointment_id={apt_id}&anomaly_type=acceptance_failed', admin_token)
    anomalies = json.loads(response.content)
    assert len(anomalies) == 1, '重复验收不通过不应创建新异常'
    second_acc_id = anomalies[0].get('acceptance_record_id')
    print(f'     异常数量={len(anomalies)}, 最新验收记录ID={second_acc_id}')
    assert second_acc_id is not None, '验收记录ID不应为空'
    if first_acc_id is not None:
        assert second_acc_id != first_acc_id or first_acc_id is None, '应更新为最新验收记录'

    print('\n  ✓ Bug修复测试5通过：重复验收不通过更新已有异常的验收记录')


def main():
    print_separator('校准异常处置模块 API 测试')
    print(f'  测试时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  测试方式: Django Test Client')
    
    try:
        test_anomaly_list()
        test_anomaly_detail()
        test_anomaly_filter()
        test_anomaly_dashboard()
        test_anomaly_role_permissions()
        test_auto_create_anomaly()
        test_anomaly_workflow()
        test_bugfix_accessory_deviation_pending()
        test_bugfix_acceptance_with_open_anomaly()
        test_bugfix_cross_appointment_validation()
        test_bugfix_invalid_filter_params()
        test_bugfix_repeated_acceptance_failure_updates_record()
        
        print_separator('测试完成')
        print('  ✓ 所有异常处置模块 API 测试已通过！')
        print('\n  异常处置模块功能总结:')
        print('  - 自动异常检测: 校准偏差、配件损坏/缺失、验收不通过自动创建异常任务')
        print('  - 五阶段处置流程: 登记→原因分析→整改措施→复核确认→结案')
        print('  - 完整处置链路: 每步操作均留痕，详情中展示完整处置历史')
        print('  - 多维度筛选: 状态、异常等级、实验区域、仪器类别、责任人等')
        print('  - 关联信息完整: 关联原校准预约、仪器、责任人、校准记录、验收记录')
        print('  - 角色权限控制: 实验员、审核员、校准员、管理员各司其职')
        print('  - 流程状态同步: 异常处置影响校准流程状态和预警状态')
        print('  - 统计汇总看板: 待处理/已结案数量，按区域/类别/等级分布')
        
    except AssertionError as e:
        print(f'\n  ✗ 测试失败: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f'\n  ✗ 发生错误: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
