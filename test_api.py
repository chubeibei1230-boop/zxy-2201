import requests
import json
from datetime import datetime, timedelta

BASE_URL = 'http://localhost:8157/api'

def print_separator(title=''):
    print('\n' + '='*60)
    if title:
        print(f'  {title}')
        print('='*60)

def print_response(response, show_body=True):
    print(f'  Status: {response.status_code}')
    if show_body and response.content:
        try:
            data = response.json()
            print(f'  Response: {json.dumps(data, ensure_ascii=False, indent=4)[:500]}')
        except:
            print(f'  Response: {response.text[:200]}')

def test_login(username, password):
    print_separator(f'测试登录 - {username}')
    response = requests.post(f'{BASE_URL}/auth/login/', json={
        'username': username,
        'password': password
    })
    print_response(response)
    if response.status_code == 200:
        data = response.json()
        return data['access']
    return None

def test_get_userinfo(token):
    print_separator('测试获取用户信息')
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f'{BASE_URL}/auth/userinfo/', headers=headers)
    print_response(response)
    return response.status_code == 200

def test_instrument_categories(token):
    print_separator('测试仪器类别 CRUD')
    headers = {'Authorization': f'Bearer {token}'}
    
    print('  GET 列表:')
    response = requests.get(f'{BASE_URL}/instrument-categories/', headers=headers)
    print_response(response)
    
    print('\n  POST 创建:')
    response = requests.post(f'{BASE_URL}/instrument-categories/', headers=headers, json={
        'name': '示波器',
        'code': 'OSC',
        'description': '各类数字示波器'
    })
    print_response(response)
    if response.status_code == 201:
        cat_id = response.json()['id']
        
        print(f'\n  GET 详情 (id={cat_id}):')
        response = requests.get(f'{BASE_URL}/instrument-categories/{cat_id}/', headers=headers)
        print_response(response)
        
        print(f'\n  PUT 更新 (id={cat_id}):')
        response = requests.put(f'{BASE_URL}/instrument-categories/{cat_id}/', headers=headers, json={
            'name': '数字示波器',
            'description': '各类数字存储示波器'
        })
        print_response(response)
        
        print(f'\n  DELETE 删除 (id={cat_id}):')
        response = requests.delete(f'{BASE_URL}/instrument-categories/{cat_id}/', headers=headers)
        print_response(response)

def test_instruments(token):
    print_separator('测试仪器管理')
    headers = {'Authorization': f'Bearer {token}'}
    
    print('  GET 列表:')
    response = requests.get(f'{BASE_URL}/instruments/', headers=headers)
    print_response(response)

def test_create_appointment(token):
    print_separator('测试创建校准预约')
    headers = {'Authorization': f'Bearer {token}'}
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print('  POST 创建预约草稿:')
    response = requests.post(f'{BASE_URL}/appointments/create/', headers=headers, json={
        'instrument_id': 1,
        'applicant': 'exp01',
        'department': '物理学院',
        'purpose': '日常维护校准，确保仪器精度',
        'expected_date': tomorrow
    })
    print_response(response)
    
    if response.status_code == 201:
        apt_id = response.json()['id']
        
        print(f'\n  GET 预约详情 (id={apt_id}):')
        response = requests.get(f'{BASE_URL}/appointments/{apt_id}/', headers=headers)
        print_response(response)
        
        return apt_id
    return None

def test_submit_appointment(token, apt_id):
    print_separator('测试提交预约审核')
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f'  POST 提交审核 (id={apt_id}):')
    response = requests.post(f'{BASE_URL}/appointments/submit/', headers=headers, json={
        'appointment_id': apt_id
    })
    print_response(response)
    return response.status_code == 200

def test_precheck(token, apt_id):
    print_separator('测试前置检查')
    headers = {'Authorization': f'Bearer {token}'}
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    print('  POST 创建前置检查记录:')
    response = requests.post(f'{BASE_URL}/prechecks/', headers=headers, json={
        'appointment_id': apt_id,
        'experimenter': 'exp01',
        'check_date': today,
        'overall_result': True,
        'items': [
            {'name': '外观检查', 'result': True, 'remark': '外观完好'},
            {'name': '电源检查', 'result': True, 'remark': '电源正常'},
            {'name': '配件齐全', 'result': True, 'remark': '配件齐全'}
        ],
        'remark': '前置检查全部通过'
    })
    print_response(response)
    return response.status_code == 201

def test_audit(token, apt_id, result='approved'):
    print_separator(f'测试审核 - {result}')
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f'  POST 审核预约 (id={apt_id}):')
    opinions = {
        'approved': '材料齐全，同意校准',
        'returned': '请补充前置检查详细数据',
        'rejected': '该仪器本月已校准，驳回申请'
    }
    response = requests.post(f'{BASE_URL}/audits/', headers=headers, json={
        'appointment_id': apt_id,
        'auditor': 'audit01',
        'result': result,
        'opinion': opinions[result]
    })
    print_response(response)
    return response.status_code == 200

def test_calibration_start(token, apt_id):
    print_separator('测试开始校准')
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f'  POST 开始校准 (id={apt_id}):')
    response = requests.post(f'{BASE_URL}/calibrations/start/', headers=headers, json={
        'appointment_id': apt_id
    })
    print_response(response)
    return response.status_code == 200

def test_calibration_record(token, apt_id):
    print_separator('测试校准记录')
    headers = {'Authorization': f'Bearer {token}'}
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print('  POST 记录校准结果:')
    response = requests.post(f'{BASE_URL}/calibrations/record/', headers=headers, json={
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
        'conclusion': '校准结果符合要求，偏差在允许范围内',
        'closing_remark': '仪器状态良好，可正常使用'
    })
    print_response(response)
    return response.status_code == 201

def test_acceptance(token, apt_id):
    print_separator('测试验收确认')
    headers = {'Authorization': f'Bearer {token}'}
    
    print(f'  POST 验收确认 (id={apt_id}):')
    response = requests.post(f'{BASE_URL}/acceptances/', headers=headers, json={
        'appointment_id': apt_id,
        'acceptor': 'exp01',
        'result': True,
        'opinion': '校准合格，同意验收'
    })
    print_response(response)
    return response.status_code == 200

def test_reports(token):
    print_separator('测试统计报表')
    headers = {'Authorization': f'Bearer {token}'}
    
    print('  GET 待审核清单:')
    response = requests.get(f'{BASE_URL}/reports/pending-audit/', headers=headers)
    print_response(response)
    
    print('\n  GET 偏差分布:')
    response = requests.get(f'{BASE_URL}/reports/deviation-distribution/', headers=headers)
    print_response(response)
    
    print('\n  GET 校准完成效率:')
    response = requests.get(f'{BASE_URL}/reports/calibration-efficiency/', headers=headers)
    print_response(response)

def test_filter(token):
    print_separator('测试筛选查询')
    headers = {'Authorization': f'Bearer {token}'}
    
    params = {
        'department': '物理学院',
        'status': 'pending_audit'
    }
    print(f'  GET 筛选 (params={params}):')
    response = requests.get(f'{BASE_URL}/appointments/filter/', headers=headers, params=params)
    print_response(response)

def test_system_check(token):
    print_separator('测试系统自动检测')
    headers = {'Authorization': f'Bearer {token}'}
    
    print('  GET 运行所有检测:')
    response = requests.get(f'{BASE_URL}/system/check/', headers=headers)
    print_response(response)

def test_duplicate_calibration(token):
    print_separator('测试重复校准检查')
    headers = {'Authorization': f'Bearer {token}'}
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    print('  第一次预约:')
    response1 = requests.post(f'{BASE_URL}/appointments/create/', headers=headers, json={
        'instrument_id': 2,
        'applicant': 'exp01',
        'department': '化学学院',
        'purpose': '测试重复预约',
        'expected_date': tomorrow
    })
    print_response(response1)
    
    if response1.status_code == 201:
        apt_id1 = response1.json()['id']
        requests.post(f'{BASE_URL}/appointments/submit/', headers=headers, json={
            'appointment_id': apt_id1
        })
        
        print(f'\n  第二次预约同一仪器同一日期 (应该失败):')
        response2 = requests.post(f'{BASE_URL}/appointments/create/', headers=headers, json={
            'instrument_id': 2,
            'applicant': 'exp02',
            'department': '化学学院',
            'purpose': '测试重复预约',
            'expected_date': tomorrow
        })
        print_response(response2)
        
        if response2.status_code == 201:
            apt_id2 = response2.json()['id']
            submit_response = requests.post(f'{BASE_URL}/appointments/submit/', headers=headers, json={
                'appointment_id': apt_id2
            })
            print(f'  提交结果 (应该失败): {submit_response.status_code}')
            print(f'  {submit_response.json()}')

def main():
    print_separator('校园仪器校准预约管理系统 API 测试')
    print(f'  测试时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  接口地址: {BASE_URL}')
    
    try:
        admin_token = test_login('admin', 'admin123')
        if not admin_token:
            print('管理员登录失败，终止测试')
            return
        test_get_userinfo(admin_token)
        
        test_instrument_categories(admin_token)
        test_instruments(admin_token)
        test_system_check(admin_token)
        
        exp_token = test_login('exp01', 'exp123')
        if exp_token:
            test_get_userinfo(exp_token)
            apt_id = test_create_appointment(exp_token)
            if apt_id:
                test_precheck(exp_token, apt_id)
                test_submit_appointment(exp_token, apt_id)
                
                audit_token = test_login('audit01', 'audit123')
                if audit_token:
                    test_audit(audit_token, apt_id, 'approved')
                
                cali_token = test_login('cali01', 'cali123')
                if cali_token:
                    test_calibration_start(cali_token, apt_id)
                    test_calibration_record(cali_token, apt_id)
                
                test_acceptance(exp_token, apt_id)
        
        test_reports(admin_token)
        test_filter(admin_token)
        test_duplicate_calibration(exp_token)
        
        print_separator('测试完成')
        print('  所有 API 测试已完成！')
        
    except requests.exceptions.ConnectionError:
        print('错误: 无法连接到服务器，请确保服务器在端口 8157 运行')
    except Exception as e:
        print(f'测试过程中发生错误: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
