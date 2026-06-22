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

def print_response(response, show_body=True):
    print(f'  Status: {response.status_code}')
    if show_body and response.content:
        try:
            data = json.loads(response.content)
            print(f'  Response: {json.dumps(data, ensure_ascii=False, indent=4)[:600]}')
        except:
            print(f'  Response: {response.content[:300]}')

def get_response_data(response, key=None):
    data = json.loads(response.content)
    if isinstance(data, dict):
        if key and key in data:
            return data[key]
        if 'data' in data:
            return data['data']
        if 'calibration' in data:
            return data['calibration']
        if 'audit' in data:
            return data['audit']
        if 'acceptance' in data:
            return data['acceptance']
        if 'appointment' in data:
            return data['appointment']
    return data

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

def test_login():
    print_separator('测试登录 API')
    response = client.post('/api/auth/login/', data={
        'username': 'admin',
        'password': 'admin123'
    }, content_type='application/json')
    print_response(response)
    assert response.status_code == 200, '登录失败'
    data = json.loads(response.content)
    assert 'access' in data, '缺少 access token'
    assert 'user' in data, '缺少 user 信息'
    print('  ✓ 登录测试通过')
    return data['access']

def test_userinfo(token):
    print_separator('测试获取用户信息')
    response = test_with_auth('GET', '/api/auth/userinfo/', token)
    print_response(response)
    assert response.status_code == 200, '获取用户信息失败'
    data = json.loads(response.content)
    assert data['role'] == 'admin', '角色错误'
    print('  ✓ 用户信息测试通过')

def test_instrument_categories_crud(token):
    print_separator('测试仪器类别 CRUD')
    
    print('  GET 列表:')
    response = test_with_auth('GET', '/api/instrument-categories/', token)
    print_response(response)
    assert response.status_code == 200, '获取列表失败'
    initial_count = len(json.loads(response.content))
    
    print('\n  POST 创建:')
    response = test_with_auth('POST', '/api/instrument-categories/', token, {
        'name': '示波器',
        'code': 'OSC',
        'description': '各类数字示波器'
    })
    print_response(response)
    assert response.status_code == 201, '创建失败'
    cat_data = json.loads(response.content)
    cat_id = cat_data['id']
    assert cat_data['name'] == '示波器', '名称错误'
    
    print(f'\n  GET 详情 (id={cat_id}):')
    response = test_with_auth('GET', f'/api/instrument-categories/{cat_id}/', token)
    print_response(response)
    assert response.status_code == 200, '获取详情失败'
    
    print(f'\n  PUT 更新 (id={cat_id}):')
    response = test_with_auth('PUT', f'/api/instrument-categories/{cat_id}/', token, {
        'name': '数字示波器',
        'description': '更新后的描述'
    })
    print_response(response)
    assert response.status_code == 200, '更新失败'
    updated = json.loads(response.content)
    assert updated['name'] == '数字示波器', '更新后名称错误'
    
    print(f'\n  DELETE 删除 (id={cat_id}):')
    response = test_with_auth('DELETE', f'/api/instrument-categories/{cat_id}/', token)
    print_response(response)
    assert response.status_code == 200, '删除失败'
    
    print('\n  ✓ 仪器类别 CRUD 测试通过')

def test_full_workflow():
    print_separator('测试完整业务流程')
    
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    print('  1. 实验员创建预约草稿:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 3,
        'applicant': 'exp01',
        'department': '物理学院',
        'purpose': '日常维护校准，确保仪器精度',
        'expected_date': tomorrow
    })
    print_response(response)
    assert response.status_code == 201, '创建预约失败'
    apt_data = json.loads(response.content)
    apt_id = apt_data['id']
    assert apt_data['status'] == 'pending_submit', '状态应为待提交'
    print(f'     预约ID: {apt_id}, 编号: {apt_data.get("appointment_no")}')
    
    print('\n  2. 实验员创建前置检查记录:')
    response = test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id,
        'experimenter': 'exp01',
        'check_date': today,
        'overall_result': True,
        'items': [
            {'name': '外观检查', 'result': True, 'remark': '外观完好'},
            {'name': '电源检查', 'result': True, 'remark': '电源正常'}
        ],
        'remark': '前置检查通过'
    })
    print_response(response)
    assert response.status_code == 201, '创建前置检查失败'
    
    print('\n  3. 实验员提交审核:')
    response = test_with_auth('POST', '/api/appointments/submit/', exp_token, {
        'appointment_id': apt_id
    })
    print_response(response)
    assert response.status_code == 200, '提交审核失败'
    apt = get_response_data(response)
    assert apt['status'] == 'pending_audit', '状态应为待审核'
    
    print('\n  4. 审核人审核通过:')
    response = test_with_auth('POST', '/api/audits/', audit_token, {
        'appointment_id': apt_id,
        'auditor': 'audit01',
        'result': 'approved',
        'opinion': '材料齐全，同意校准'
    })
    print_response(response)
    assert response.status_code == 200, '审核失败'
    apt = get_response_data(response, key='appointment')
    assert apt['status'] == 'pending_calibration', '状态应为待校准'
    
    print('\n  5. 校准员开始校准:')
    response = test_with_auth('POST', '/api/calibrations/start/', cali_token, {
        'appointment_id': apt_id
    })
    print_response(response)
    assert response.status_code == 200, '开始校准失败'
    apt = get_response_data(response)
    assert apt['status'] == 'calibrating', '状态应为校准中'
    
    print('\n  6. 校准员记录校准结果:')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    response = test_with_auth('POST', '/api/calibrations/record/', cali_token, {
        'appointment_id': apt_id,
        'calibrator': 'cali01',
        'start_date': now,
        'end_date': now,
        'standard_value': 100.0,
        'measured_value': 99.9999,
        'deviation_level': 'none',
        'accessory_status': 'normal',
        'environment_temp': 23.5,
        'environment_humidity': 45.0,
        'calibration_method': '砝码比较法',
        'conclusion': '校准结果符合要求',
        'closing_remark': '仪器状态良好'
    })
    print_response(response)
    assert response.status_code in [200, 201], '记录校准结果失败'
    cali_data = get_response_data(response, key='calibration')
    assert abs(cali_data['error_value'] - (-0.0001)) < 0.00001, '误差计算错误'
    
    print('\n  7. 实验员验收确认:')
    response = test_with_auth('POST', '/api/acceptances/', exp_token, {
        'appointment_id': apt_id,
        'acceptor': 'exp01',
        'result': True,
        'opinion': '校准合格，同意验收'
    })
    print_response(response)
    assert response.status_code == 200, '验收失败'
    apt = get_response_data(response, key='appointment')
    assert apt['status'] == 'closed', '状态应为已结案'
    
    print('\n  ✓ 完整业务流程测试通过！')
    return apt_id

def test_duplicate_calibration_check():
    print_separator('测试重复校准检查')
    exp_token = get_auth_token('exp01')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print('  创建第一个预约:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 2,
        'applicant': 'exp01',
        'department': '化学学院',
        'purpose': '测试重复预约1',
        'expected_date': tomorrow
    })
    assert response.status_code == 201
    apt1 = json.loads(response.content)
    
    print('  为第一个预约创建前置检查:')
    response = test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt1['id'],
        'experimenter': 'exp01',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [
            {'name': '外观检查', 'result': True, 'remark': '正常'},
            {'name': '电源检查', 'result': True, 'remark': '正常'}
        ],
        'overall_result': True,
        'remark': '检查通过'
    })
    assert response.status_code == 201
    
    print('  提交第一个预约:')
    response = test_with_auth('POST', '/api/appointments/submit/', exp_token, {
        'appointment_id': apt1['id']
    })
    assert response.status_code == 200
    
    print('\n  直接创建第二个预约（同一仪器同一日期，应该失败）:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 2,
        'applicant': 'exp02',
        'department': '化学学院',
        'purpose': '测试重复预约2',
        'expected_date': tomorrow
    })
    print_response(response)
    assert response.status_code == 400, '应该阻止重复预约创建'
    data = json.loads(response.content)
    assert '重复' in data.get('detail', '') or '已有' in data.get('detail', ''), '错误信息应包含重复提示'
    
    print('\n  ✓ 重复校准检查测试通过！')

def test_reports(token):
    print_separator('测试统计报表')
    
    print('  待审核清单:')
    response = test_with_auth('GET', '/api/reports/pending-audit/', token)
    print_response(response)
    assert response.status_code == 200
    
    print('\n  偏差分布:')
    response = test_with_auth('GET', '/api/reports/deviation-distribution/', token)
    print_response(response)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'overall' in data
    assert 'by_region' in data
    assert 'by_category' in data
    
    print('\n  校准完成效率:')
    response = test_with_auth('GET', '/api/reports/calibration-efficiency/', token)
    print_response(response)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'total' in data
    assert 'closed' in data
    assert 'completion_rate' in data
    
    print('\n  ✓ 统计报表测试通过！')

def test_filters(token):
    print_separator('测试筛选查询')
    
    params = {'department': '物理学院', 'status': 'closed'}
    print(f'  按部门和状态筛选: {params}')
    response = test_with_auth('GET', '/api/appointments/filter/', token, params)
    print_response(response)
    assert response.status_code == 200
    
    print('\n  ✓ 筛选查询测试通过！')

def test_system_check(token):
    print_separator('测试系统自动检测')
    
    response = test_with_auth('GET', '/api/system/check/', token)
    print_response(response)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert 'audit_timeout' in data
    assert 'precheck_missing' in data
    assert 'region_deviation' in data
    assert 'accessory_unclosed' in data
    assert 'storage_conflict' in data
    
    print('\n  ✓ 系统自动检测测试通过！')

def test_role_permissions():
    print_separator('测试角色权限控制')
    
    exp_token = get_auth_token('exp01')
    admin_token = get_auth_token('admin')
    
    print('  实验员尝试创建仪器类别（应该失败）:')
    response = test_with_auth('POST', '/api/instrument-categories/', exp_token, {
        'name': '测试', 'code': 'TEST'
    })
    print_response(response)
    assert response.status_code == 403, '实验员不应有权限创建仪器类别'
    
    print('\n  管理员创建仪器类别（应该成功）:')
    response = test_with_auth('POST', '/api/instrument-categories/', admin_token, {
        'name': '权限测试', 'code': 'PERM'
    })
    print_response(response)
    assert response.status_code == 201, '管理员应该有权限'
    cat_id = json.loads(response.content)['id']
    
    print(f'\n  清理测试数据 (id={cat_id}):')
    test_with_auth('DELETE', f'/api/instrument-categories/{cat_id}/', admin_token)
    
    print('\n  ✓ 角色权限控制测试通过！')

def test_precheck_required():
    print_separator('测试前置检查必填验证')
    exp_token = get_auth_token('exp01')
    day_after_tomorrow = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
    
    print('  创建预约（无前检查）:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 5,
        'applicant': 'exp01',
        'department': '生物学院',
        'purpose': '测试前置检查必填',
        'expected_date': day_after_tomorrow
    })
    assert response.status_code == 201
    apt = json.loads(response.content)
    apt_id = apt['id']
    
    print('  无前检查直接提交审核（应该失败）:')
    response = test_with_auth('POST', '/api/appointments/submit/', exp_token, {
        'appointment_id': apt_id
    })
    print_response(response)
    assert response.status_code == 400, '无前检查应无法提交审核'
    data = json.loads(response.content)
    assert '前置检查' in data.get('detail', ''), '错误信息应包含前置检查提示'
    
    print('\n  ✓ 前置检查必填验证测试通过！')

def test_rejected_status():
    print_separator('测试审核驳回独立状态')
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    day_after_tomorrow = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    
    print('  实验员创建预约:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 5,
        'applicant': 'exp01',
        'department': '生物学院',
        'purpose': '测试驳回状态',
        'expected_date': day_after_tomorrow
    })
    apt_id = json.loads(response.content)['id']
    
    print('  创建前置检查:')
    test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id,
        'experimenter': 'exp01',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [{'name': '外观检查', 'result': True, 'remark': '正常'}],
        'overall_result': True,
        'remark': '检查通过'
    })
    
    print('  提交审核:')
    test_with_auth('POST', '/api/appointments/submit/', exp_token, {'appointment_id': apt_id})
    
    print('  审核人驳回:')
    response = test_with_auth('POST', '/api/audits/', audit_token, {
        'appointment_id': apt_id,
        'auditor': 'audit01',
        'result': 'rejected',
        'opinion': '材料不齐全，予以驳回'
    })
    print_response(response)
    assert response.status_code == 200
    apt = get_response_data(response, key='appointment')
    assert apt['status'] == 'rejected', '驳回后状态应为 rejected（已驳回），不应是 closed（已结案）'
    
    print('\n  ✓ 审核驳回独立状态测试通过！')

def test_audit_status_filter():
    print_separator('测试审核状态筛选')
    admin_token = get_auth_token('admin')
    
    print('  按审核状态=通过筛选:')
    response = test_with_auth('GET', '/api/appointments/filter/?audit_status=approved', admin_token)
    print_response(response)
    assert response.status_code == 200
    
    print('  按仪器状态=active筛选:')
    response = test_with_auth('GET', '/api/appointments/filter/?instrument_status=active', admin_token)
    print_response(response)
    assert response.status_code == 200
    data = json.loads(response.content)
    assert isinstance(data, list)
    
    print('\n  ✓ 审核状态和仪器状态筛选测试通过！')

def test_deviation_duplicate_check():
    print_separator('测试偏差待处理状态重复预约拦截')
    exp_token = get_auth_token('exp01')
    cali_token = get_auth_token('cali01')
    future_date = (datetime.now() + timedelta(days=4)).strftime('%Y-%m-%d')
    
    print('  创建第一个预约:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 6,
        'applicant': 'exp01',
        'department': '环境学院',
        'purpose': '测试偏差状态重复预约',
        'expected_date': future_date
    })
    apt_id = json.loads(response.content)['id']
    
    print('  创建前置检查并提交审核、通过审核:')
    test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id,
        'experimenter': 'exp01',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [{'name': '外观检查', 'result': True, 'remark': '正常'}],
        'overall_result': True,
        'remark': '检查通过'
    })
    test_with_auth('POST', '/api/appointments/submit/', exp_token, {'appointment_id': apt_id})
    
    audit_token = get_auth_token('audit01')
    test_with_auth('POST', '/api/audits/', audit_token, {
        'appointment_id': apt_id,
        'auditor': 'audit01',
        'result': 'approved',
        'opinion': '通过'
    })
    
    print('  开始校准并记录偏差结果:')
    test_with_auth('POST', '/api/calibrations/start/', cali_token, {'appointment_id': apt_id})
    test_with_auth('POST', '/api/calibrations/record/', cali_token, {
        'appointment_id': apt_id,
        'calibrator': 'cali01',
        'start_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'end_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'standard_value': 100.0,
        'measured_value': 95.0,
        'deviation_level': 'major',
        'accessory_status': 'normal',
        'environment_temp': 23.5,
        'environment_humidity': 45.0,
        'calibration_method': '标准方法',
        'conclusion': '偏差较大，待处理',
        'closing_remark': '偏差待处理'
    })
    
    print('  尝试创建同一仪器同一日期的第二个预约（应该失败）:')
    response = test_with_auth('POST', '/api/appointments/create/', exp_token, {
        'instrument_id': 6,
        'applicant': 'exp02',
        'department': '环境学院',
        'purpose': '重复预约测试',
        'expected_date': future_date
    })
    print_response(response)
    assert response.status_code == 400, '偏差待处理状态应拦截重复预约'
    
    print('\n  ✓ 偏差待处理状态重复预约拦截测试通过！')


def test_warning_detection_and_list():
    print_separator('测试预警识别与列表')
    admin_token = get_auth_token('admin')
    
    print('  触发预警检测:')
    response = test_with_auth('POST', '/api/warnings/detect/', admin_token)
    print_response(response)
    assert response.status_code == 200, '预警检测失败'
    data = json.loads(response.content)
    print(f'     生成预警数量: {data.get("generated_count", 0)}')
    assert data.get('generated_count', 0) > 0, '应至少生成一条预警'
    
    print('\n  获取预警列表:')
    response = test_with_auth('GET', '/api/warnings/', admin_token)
    print_response(response)
    assert response.status_code == 200, '获取预警列表失败'
    warnings = json.loads(response.content)
    assert isinstance(warnings, list), '返回应为列表'
    assert len(warnings) > 0, '预警列表不应为空'
    
    levels = set(w.get('level') for w in warnings)
    print(f'     预警级别覆盖: {levels}')
    assert len(levels) > 0, '应至少有一个预警级别'
    
    for w in warnings:
        assert 'instrument' in w, '应包含仪器信息'
        assert 'level_label' in w, '应包含级别标签'
        assert 'status_label' in w, '应包含状态标签'
    
    print('\n  按级别筛选 (overdue):')
    response = test_with_auth('GET', '/api/warnings/?level=overdue', admin_token)
    assert response.status_code == 200
    overdue_list = json.loads(response.content)
    print(f'     超期预警数量: {len(overdue_list)}')
    for w in overdue_list:
        assert w.get('level') == 'overdue'
    
    print('\n  按状态筛选 (unhandled):')
    response = test_with_auth('GET', '/api/warnings/?status=unhandled', admin_token)
    assert response.status_code == 200
    unhandled_list = json.loads(response.content)
    print(f'     未处理预警数量: {len(unhandled_list)}')
    for w in unhandled_list:
        assert w.get('status') == 'unhandled'
    
    print('\n  ✓ 预警识别与列表测试通过！')


def test_warning_detail():
    print_separator('测试预警详情')
    admin_token = get_auth_token('admin')
    
    response = test_with_auth('GET', '/api/warnings/', admin_token)
    warnings = json.loads(response.content)
    assert len(warnings) > 0, '预警列表不应为空'
    warning_id = warnings[0]['id']
    
    print(f'  获取预警详情 (id={warning_id}):')
    response = test_with_auth('GET', f'/api/warnings/{warning_id}/', admin_token)
    print_response(response)
    assert response.status_code == 200, '获取预警详情失败'
    detail = json.loads(response.content)
    
    assert 'instrument' in detail, '应包含仪器信息'
    assert 'category' in detail, '应包含类别信息'
    assert 'region' in detail, '应包含区域信息'
    assert 'responsible_person' in detail, '应包含责任人信息'
    assert 'rule' in detail, '应包含规则信息'
    assert 'level_label' in detail, '应包含级别标签'
    assert 'status_label' in detail, '应包含状态标签'
    assert 'next_calibration_date' in detail, '应包含下次校准日期'
    assert 'last_calibration_date' in detail, '应包含上次校准日期'
    assert 'has_unfinished_flow' in detail, '应包含未完结流程标记'
    
    print('\n  ✓ 预警详情测试通过！')


def test_warning_create_appointment():
    print_separator('测试预警快速发起续检申请')
    exp_token = get_auth_token('exp01')
    admin_token = get_auth_token('admin')
    
    response = test_with_auth('GET', '/api/warnings/?status=unhandled', admin_token)
    unhandled = json.loads(response.content)
    assert len(unhandled) > 0, '应有未处理的预警'
    
    target_warning = None
    for w in unhandled:
        if not w.get('has_unfinished_flow'):
            target_warning = w
            break
    assert target_warning is not None, '应找到可申请的预警'
    warning_id = target_warning['id']
    instrument_id = target_warning['instrument']['id']
    print(f'  选择预警 id={warning_id}, 仪器 id={instrument_id}')
    
    print('  实验员发起续检申请:')
    response = test_with_auth('POST', '/api/warnings/create-appointment/', exp_token, {
        'warning_id': warning_id,
        'purpose': '仪器到期预警触发的续检申请，确保仪器精度'
    })
    print_response(response)
    assert response.status_code == 201, '续检申请创建失败'
    result = json.loads(response.content)
    assert 'appointment' in result
    apt = result['appointment']
    apt_id = apt['id']
    print(f'     生成预约 id={apt_id}, 编号={apt.get("appointment_no")}')
    assert apt.get('from_warning') == True, '预约应标记为来自预警'
    assert apt.get('warning_id') == warning_id, '预约应关联预警ID'
    assert apt.get('instrument_id') == instrument_id, '预约应关联正确的仪器'
    
    print('\n  查看预警状态变更:')
    response = test_with_auth('GET', f'/api/warnings/{warning_id}/', admin_token)
    warning_detail = json.loads(response.content)
    print(f'     预警状态: {warning_detail.get("status")} - {warning_detail.get("status_label")}')
    assert warning_detail.get('status') == 'processing', '预警状态应为处理中'
    assert warning_detail.get('appointment_id') == apt_id, '预警应关联预约ID'
    
    print('\n  查看预约详情中的预警标记:')
    response = test_with_auth('GET', f'/api/appointments/{apt_id}/', exp_token)
    apt_detail = json.loads(response.content)
    assert apt_detail.get('from_warning') == True, '预约详情应包含预警来源标记'
    assert apt_detail.get('warning_id') == warning_id, '预约详情应包含预警ID'
    print('     ✓ 预约详情正确显示预警来源标记')
    
    print('\n  ✓ 预警快速发起续检申请测试通过！')
    return warning_id, apt_id


def test_warning_duplicate_block():
    print_separator('测试预警重复申请拦截')
    exp_token = get_auth_token('exp01')
    exp_token2 = get_auth_token('exp02')
    admin_token = get_auth_token('admin')
    
    response = test_with_auth('GET', '/api/warnings/?status=unhandled', admin_token)
    unhandled = json.loads(response.content)
    
    target_warning = None
    for w in unhandled:
        if not w.get('has_unfinished_flow'):
            target_warning = w
            break
    assert target_warning is not None, '应找到可申请的预警'
    warning_id = target_warning['id']
    
    print('  第一个实验员发起续检申请:')
    response = test_with_auth('POST', '/api/warnings/create-appointment/', exp_token, {
        'warning_id': warning_id,
        'purpose': '第一次申请'
    })
    assert response.status_code == 201
    
    print('  第二个实验员尝试对同一预警发起申请（应该失败）:')
    response = test_with_auth('POST', '/api/warnings/create-appointment/', exp_token2, {
        'warning_id': warning_id,
        'purpose': '重复申请'
    })
    print_response(response)
    assert response.status_code == 400, '应拦截重复申请'
    data = json.loads(response.content)
    assert '已存在未完结' in data.get('detail', '') or '处理' in data.get('detail', ''), \
        '错误信息应提示未完结流程'
    
    print('\n  ✓ 预警重复申请拦截测试通过！')


def test_warning_full_workflow():
    print_separator('测试预警续检完整闭环流程')
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')
    
    response = test_with_auth('GET', '/api/warnings/?status=unhandled', admin_token)
    unhandled = json.loads(response.content)
    
    target_warning = None
    for w in unhandled:
        if not w.get('has_unfinished_flow'):
            target_warning = w
            break
    assert target_warning is not None, '应找到可申请的预警'
    warning_id = target_warning['id']
    print(f'  选择预警 id={warning_id}')
    
    print('  1. 实验员发起续检申请:')
    response = test_with_auth('POST', '/api/warnings/create-appointment/', exp_token, {
        'warning_id': warning_id,
        'purpose': '预警触发的完整闭环测试'
    })
    assert response.status_code == 201
    apt_id = json.loads(response.content)['appointment']['id']
    
    print('  2. 创建前置检查:')
    response = test_with_auth('POST', '/api/prechecks/', exp_token, {
        'appointment_id': apt_id,
        'experimenter': 'exp01',
        'check_date': datetime.now().strftime('%Y-%m-%d'),
        'items': [
            {'name': '外观检查', 'result': True, 'remark': '正常'},
            {'name': '电源检查', 'result': True, 'remark': '正常'}
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
        'auditor': 'audit01',
        'result': 'approved',
        'opinion': '同意续检校准'
    })
    assert response.status_code == 200
    
    print('  5. 开始校准:')
    response = test_with_auth('POST', '/api/calibrations/start/', cali_token, {
        'appointment_id': apt_id
    })
    assert response.status_code == 200
    
    print('  6. 记录校准结果:')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    response = test_with_auth('POST', '/api/calibrations/record/', cali_token, {
        'appointment_id': apt_id,
        'calibrator': 'cali01',
        'start_date': now,
        'end_date': now,
        'standard_value': 100.0,
        'measured_value': 100.0,
        'deviation_level': 'none',
        'accessory_status': 'normal',
        'environment_temp': 23.5,
        'environment_humidity': 45.0,
        'calibration_method': '标准方法',
        'conclusion': '校准合格',
        'closing_remark': '仪器状态良好'
    })
    assert response.status_code in [200, 201]
    
    print('  7. 验收确认:')
    response = test_with_auth('POST', '/api/acceptances/', exp_token, {
        'appointment_id': apt_id,
        'acceptor': 'exp01',
        'result': True,
        'opinion': '校准合格，同意验收'
    })
    assert response.status_code == 200
    
    print('\n  8. 检查预警状态（应变为已处理）:')
    response = test_with_auth('GET', f'/api/warnings/{warning_id}/', admin_token)
    warning_detail = json.loads(response.content)
    print(f'     预警状态: {warning_detail.get("status")} - {warning_detail.get("status_label")}')
    assert warning_detail.get('status') == 'handled', '流程完成后预警状态应变为已处理'
    
    print('\n  9. 检查预约详情中的预警标记:')
    response = test_with_auth('GET', f'/api/appointments/{apt_id}/', admin_token)
    apt_detail = json.loads(response.content)
    assert apt_detail.get('from_warning') == True
    assert apt_detail.get('warning_id') == warning_id
    print('     ✓ 预约详情保留预警来源标记')
    
    print('\n  ✓ 预警续检完整闭环流程测试通过！')


def test_warning_dashboard():
    print_separator('测试预警汇总看板')
    admin_token = get_auth_token('admin')
    
    print('  获取预警看板数据:')
    response = test_with_auth('GET', '/api/warnings/dashboard/', admin_token)
    print_response(response)
    assert response.status_code == 200, '获取看板数据失败'
    dashboard = json.loads(response.content)
    
    assert 'summary' in dashboard, '应包含汇总数据'
    summary = dashboard['summary']
    print(f'     汇总: {json.dumps(summary, ensure_ascii=False)}')
    assert 'total' in summary
    assert 'approaching' in summary
    assert 'expired' in summary
    assert 'overdue' in summary
    assert 'unhandled' in summary
    assert 'processing' in summary
    assert 'handled' in summary
    assert summary['total'] == summary['approaching'] + summary['expired'] + summary['overdue']
    
    assert 'by_region' in dashboard, '应包含按区域统计'
    by_region = dashboard['by_region']
    print(f'     按区域维度: {list(by_region.keys())}')
    for region_name, stats in by_region.items():
        assert 'total' in stats
        assert 'approaching' in stats
        assert 'expired' in stats
        assert 'overdue' in stats
        assert 'unhandled' in stats
        assert 'processing' in stats
        assert 'handled' in stats
    
    assert 'by_category' in dashboard, '应包含按类别统计'
    by_category = dashboard['by_category']
    print(f'     按类别维度: {list(by_category.keys())}')
    
    assert 'by_responsible_person' in dashboard, '应包含按责任人统计'
    by_person = dashboard['by_responsible_person']
    print(f'     按责任人维度: {list(by_person.keys())}')
    
    assert 'generated_at' in dashboard, '应包含生成时间'
    
    print('\n  ✓ 预警汇总看板测试通过！')


def test_warning_role_permissions():
    print_separator('测试预警模块角色权限')
    
    exp_token = get_auth_token('exp01')
    audit_token = get_auth_token('audit01')
    cali_token = get_auth_token('cali01')
    admin_token = get_auth_token('admin')
    
    print('  预警列表 - 各角色均可访问:')
    for role, token in [('实验员', exp_token), ('审核人', audit_token), ('校准员', cali_token), ('管理员', admin_token)]:
        response = test_with_auth('GET', '/api/warnings/', token)
        assert response.status_code == 200, f'{role}应能访问预警列表'
    print('     ✓ 所有角色均可访问预警列表')
    
    print('  预警看板 - 仅管理员可访问:')
    response = test_with_auth('GET', '/api/warnings/dashboard/', exp_token)
    assert response.status_code == 403, '实验员不应访问看板'
    response = test_with_auth('GET', '/api/warnings/dashboard/', audit_token)
    assert response.status_code == 403, '审核人不应访问看板'
    response = test_with_auth('GET', '/api/warnings/dashboard/', cali_token)
    assert response.status_code == 403, '校准员不应访问看板'
    response = test_with_auth('GET', '/api/warnings/dashboard/', admin_token)
    assert response.status_code == 200, '管理员应能访问看板'
    print('     ✓ 仅管理员可访问预警看板')
    
    print('  发起续检申请 - 仅实验员可访问:')
    response = test_with_auth('GET', '/api/warnings/', admin_token)
    warnings = json.loads(response.content)
    assert len(warnings) > 0
    test_data = {'warning_id': warnings[0]['id'], 'purpose': '权限测试'}
    
    response = test_with_auth('POST', '/api/warnings/create-appointment/', audit_token, test_data)
    assert response.status_code == 403, '审核人不应发起申请'
    response = test_with_auth('POST', '/api/warnings/create-appointment/', cali_token, test_data)
    assert response.status_code == 403, '校准员不应发起申请'
    response = test_with_auth('POST', '/api/warnings/create-appointment/', admin_token, test_data)
    assert response.status_code == 403, '管理员不应发起申请'
    print('     ✓ 仅实验员可发起续检申请')
    
    print('  预警检测 - 仅管理员可访问:')
    response = test_with_auth('POST', '/api/warnings/detect/', exp_token)
    assert response.status_code == 403, '实验员不应触发检测'
    response = test_with_auth('POST', '/api/warnings/detect/', admin_token)
    assert response.status_code == 200, '管理员应能触发检测'
    print('     ✓ 仅管理员可触发预警检测')
    
    print('\n  ✓ 预警模块角色权限测试通过！')

def main():
    print_separator('校园仪器校准预约管理系统 API 测试')
    print(f'  测试时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  测试方式: Django Test Client')
    
    try:
        admin_token = test_login()
        test_userinfo(admin_token)
        test_instrument_categories_crud(admin_token)
        test_full_workflow()
        test_duplicate_calibration_check()
        test_reports(admin_token)
        test_filters(admin_token)
        test_system_check(admin_token)
        test_role_permissions()
        test_precheck_required()
        test_rejected_status()
        test_audit_status_filter()
        test_deviation_duplicate_check()
        
        test_warning_detection_and_list()
        test_warning_detail()
        test_warning_create_appointment()
        test_warning_duplicate_block()
        test_warning_full_workflow()
        test_warning_dashboard()
        test_warning_role_permissions()
        
        print_separator('测试完成')
        print('  ✓ 所有 API 测试已通过！')
        print('\n  系统功能总结:')
        print('  - 用户认证: JWT 登录，支持4种角色')
        print('  - 基础数据管理: 仪器类别、区域、位置、责任人、规则、仪器')
        print('  - 业务流程: 预约→前置检查→审核→校准→验收→结案')
        print('  - 状态流转: 7种状态，严格控制')
        print('  - 业务规则: 重复校准检查、5种自动检测')
        print('  - 统计报表: 待审核清单、偏差分布、校准效率')
        print('  - 权限控制: 基于角色的访问控制')
        print('  - 数据持久化: TinyDB JSON 文件存储')
        print('  - 仪器到期预警与续检闭环:')
        print('      * 自动识别临近到期/已到期/超期仪器')
        print('      * 预警列表筛选、状态标识、详情查看')
        print('      * 实验员快速发起续检申请并填写使用目的')
        print('      * 未完结流程自动拦截重复发起')
        print('      * 流程详情展示预警来源标记')
        print('      * 管理员汇总看板（区域/类别/负责人维度）')
        print('      * 已处理/处理中/未处理预警状态区分')
        
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
