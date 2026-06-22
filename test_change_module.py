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
    print('\n' + '=' * 60)
    if title:
        print(f'  {title}')
        print('=' * 60)


def print_response(response, show_body=True, max_len=800):
    print(f'  Status: {response.status_code}')
    if show_body and response.content:
        try:
            data = json.loads(response.content)
            content = json.dumps(data, ensure_ascii=False, indent=2)
            if len(content) > max_len:
                content = content[:max_len] + '...'
            print(f'  Response: {content}')
        except:
            content = str(response.content[:max_len])
            if len(response.content) > max_len:
                content += '...'
            print(f'  Response: {content}')


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


def test_login(username, password):
    print_separator(f'测试登录 - {username}')
    response = client.post('/api/auth/login/', data={
        'username': username,
        'password': password
    }, content_type='application/json')
    print_response(response)
    assert response.status_code == 200, f'{username} 登录失败'
    data = json.loads(response.content)
    assert 'access' in data, '缺少 access token'
    print(f'  ✓ {username} 登录测试通过')
    return data['access']


def test_get_appointment_for_change(token):
    print_separator('获取可变更的预约')
    response = test_with_auth('GET', '/api/appointments/', token)
    print_response(response, show_body=False)
    assert response.status_code == 200, '获取预约列表失败'
    appointments = json.loads(response.content)

    target_apt = None
    for apt in appointments:
        if apt.get('status') in ['pending_audit', 'pending_calibration', 'calibrating', 'pending_acceptance']:
            target_apt = apt
            break

    if not target_apt and appointments:
        target_apt = appointments[0]

    if target_apt:
        print(f'  找到预约: ID={target_apt["id"]}, 状态={target_apt.get("status")}')
        return target_apt['id']
    return None


def test_create_change_request(token, appointment_id):
    print_separator('测试创建变更申请')

    if not appointment_id:
        print('  ⚠ 没有找到可变更的预约，跳过创建测试')
        return None

    change_data = {
        'appointment_id': appointment_id,
        'change_type': 'expected_date',
        'old_value': '2024-06-20',
        'new_value': '2024-06-25',
        'reason': '实验员临时有其他任务，需要调整校准日期',
        'expected_effective_date': '2024-06-25'
    }

    response = test_with_auth('POST', '/api/changes/create/', token, change_data)
    print_response(response)
    assert response.status_code == 201, '创建变更申请失败'
    data = json.loads(response.content)
    assert 'id' in data, '缺少变更申请ID'
    assert data['status'] == 'pending_audit', '状态应该是待审核'
    print('  ✓ 创建变更申请测试通过')
    return data['id']


def test_get_change_list(token):
    print_separator('测试获取变更申请列表')
    response = test_with_auth('GET', '/api/changes/', token)
    print_response(response, show_body=False)
    assert response.status_code == 200, '获取变更列表失败'
    data = json.loads(response.content)
    print(f'  共 {len(data)} 条变更申请')
    if data:
        print(f'  最新变更: {data[0].get("change_no")} - {data[0].get("change_type_label")}')
    print('  ✓ 获取变更列表测试通过')
    return data[0]['id'] if data else None


def test_get_change_detail(token, change_id):
    print_separator('测试获取变更申请详情')
    if not change_id:
        print('  ⚠ 没有变更申请ID，跳过详情测试')
        return

    response = test_with_auth('GET', f'/api/changes/{change_id}/', token)
    print_response(response)
    assert response.status_code == 200, '获取变更详情失败'
    data = json.loads(response.content)
    assert 'appointment' in data, '缺少预约信息'
    assert 'instrument' in data, '缺少仪器信息'
    assert 'audit_records' in data, '缺少审批记录'
    print('  ✓ 获取变更详情测试通过')


def test_audit_change_request(admin_token, change_id):
    print_separator('测试审核变更申请')
    if not change_id:
        print('  ⚠ 没有变更申请ID，跳过审核测试')
        return

    audit_data = {
        'change_request_id': change_id,
        'result': 'approved',
        'opinion': '同意调整，情况属实'
    }

    response = test_with_auth('POST', '/api/changes/audit/', admin_token, audit_data)
    print_response(response)
    assert response.status_code == 200, '审核变更申请失败'
    data = json.loads(response.content)
    assert data['data']['status'] == 'approved', '状态应该是已通过'
    print('  ✓ 审核变更申请测试通过')


def test_filter_changes(token):
    print_separator('测试筛选变更申请')

    filters = [
        {'status': 'approved'},
        {'change_type': 'expected_date'},
    ]

    for f in filters:
        response = test_with_auth('GET', '/api/changes/', token, f)
        assert response.status_code == 200, f'筛选失败: {f}'
        data = json.loads(response.content)
        print(f'  筛选条件 {f}: {len(data)} 条结果')

    print('  ✓ 筛选变更申请测试通过')


def test_get_appointment_change_history(token, appointment_id):
    print_separator('测试获取预约变更历史')
    if not appointment_id:
        print('  ⚠ 没有预约ID，跳过变更历史测试')
        return

    response = test_with_auth('GET', f'/api/appointments/{appointment_id}/change-history/', token)
    print_response(response)
    assert response.status_code == 200, '获取变更历史失败'
    data = json.loads(response.content)
    print(f'  该预约共有 {len(data)} 条变更记录')
    print('  ✓ 获取预约变更历史测试通过')


def test_appointment_detail_includes_history(token, appointment_id):
    print_separator('测试预约详情包含变更历史')
    if not appointment_id:
        print('  ⚠ 没有预约ID，跳过测试')
        return

    response = test_with_auth('GET', f'/api/appointments/{appointment_id}/', token)
    assert response.status_code == 200, '获取预约详情失败'
    data = json.loads(response.content)
    assert 'change_history' in data, '预约详情应该包含变更历史'
    print(f'  预约详情包含 {len(data["change_history"])} 条变更历史')
    print('  ✓ 预约详情包含变更历史测试通过')


def test_permission_control():
    print_separator('测试权限控制')

    admin_token = get_auth_token('admin')
    experimenter_token = get_auth_token('exp01')
    calibrator_token = get_auth_token('cali01')

    appointment_id = test_get_appointment_for_change(experimenter_token)

    if appointment_id:
        print('  1. 测试校准员创建变更申请（应该失败）')
        change_data = {
            'appointment_id': appointment_id,
            'change_type': 'expected_date',
            'old_value': '2024-06-20',
            'new_value': '2024-06-26',
            'reason': '测试权限控制'
        }
        response = test_with_auth('POST', '/api/changes/create/', calibrator_token, change_data)
        print(f'    状态码: {response.status_code} (预期 403)')
        assert response.status_code == 403, '校准员不应该能创建变更申请'
        print('    ✓ 校准员创建变更申请被正确拒绝')

        print('  2. 测试实验员审核变更申请（应该失败）')
        change_id = test_create_change_request(experimenter_token, appointment_id)
        if change_id:
            audit_data = {
                'change_request_id': change_id,
                'result': 'approved',
                'opinion': '实验员越权审核'
            }
            response = test_with_auth('POST', '/api/changes/audit/', experimenter_token, audit_data)
            print(f'    状态码: {response.status_code} (预期 403)')
            assert response.status_code == 403, '实验员不应该能审核变更申请'
            print('    ✓ 实验员审核变更申请被正确拒绝')

    print('  ✓ 权限控制测试通过')


def main():
    print_separator('变更申请模块完整测试')
    print('  测试流程: 登录 → 创建变更 → 查询列表 → 查询详情 → ')
    print('           审核变更 → 筛选查询 → 查看变更历史 → 权限验证')
    print('=' * 60)

    try:
        admin_token = test_login('admin', 'admin123')
        experimenter_token = test_login('exp01', 'exp123')
        auditor_token = test_login('audit01', 'audit123')

        appointment_id = test_get_appointment_for_change(experimenter_token)

        change_id = test_create_change_request(experimenter_token, appointment_id)

        list_change_id = test_get_change_list(experimenter_token)

        test_get_change_detail(experimenter_token, change_id or list_change_id)

        test_audit_change_request(auditor_token, change_id or list_change_id)

        test_filter_changes(admin_token)

        test_get_appointment_change_history(experimenter_token, appointment_id)

        test_appointment_detail_includes_history(experimenter_token, appointment_id)

        test_permission_control()

        print_separator('所有测试通过!')
        print('  ✓ 变更申请模块功能完整')
        print('  ✓ 支持创建、查询、审批、筛选')
        print('  ✓ 权限控制正确')
        print('  ✓ 变更历史完整记录')
        print('=' * 60)

    except AssertionError as e:
        print(f'\n  ✗ 测试失败: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\n  ✗ 发生错误: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
