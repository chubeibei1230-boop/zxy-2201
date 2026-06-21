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
