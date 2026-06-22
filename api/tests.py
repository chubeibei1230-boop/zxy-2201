from django.test import TestCase, Client
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime, timedelta
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from api.database import (
    instruments_table, calibration_warnings_table,
    calibration_appointments_table, users_table,
    InstrumentQuery, CalibrationWarningQuery,
    CalibrationAppointmentQuery, UserQuery,
    generate_id, now_str
)
from api.services import (
    get_warning_level, get_instrument_next_calibration_date,
    get_instrument_last_calibration_date, run_warning_detection,
    list_warnings, get_warning_full_info, create_warning_appointment,
    get_warning_dashboard, has_unfinished_flow,
    update_warning_status_from_appointment, reset_warning_status_by_id,
    WARNING_APPROACHING_DAYS
)
from api.auth_backend import hash_password


def get_token_for_user(username):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        user = User(username=username)
        user.set_unusable_password()
        user.is_active = True
        user.save()
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class WarningLevelCalculationTest(TestCase):
    """测试预警级别计算逻辑"""

    @classmethod
    def setUpTestData(cls):
        cls.instrument_id = 1

    def test_overdue_negative_days(self):
        """超期未处理：下次校准日期在过去"""
        from unittest.mock import patch
        with patch('api.services.get_instrument_next_calibration_date') as mock_next:
            mock_next.return_value = datetime.now() - timedelta(days=5)
            level = get_warning_level(self.instrument_id)
            self.assertEqual(level, 'overdue')

    def test_expired_zero_days(self):
        """已到期：下次校准日期就是今天"""
        from unittest.mock import patch
        with patch('api.services.get_instrument_next_calibration_date') as mock_next:
            mock_next.return_value = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            level = get_warning_level(self.instrument_id)
            self.assertEqual(level, 'expired')

    def test_approaching_positive_within_threshold(self):
        """临近到期：距离下次校准还有15天（在30天阈值内）"""
        from unittest.mock import patch
        with patch('api.services.get_instrument_next_calibration_date') as mock_next:
            mock_next.return_value = datetime.now() + timedelta(days=15)
            level = get_warning_level(self.instrument_id)
            self.assertEqual(level, 'approaching')

    def test_approaching_at_threshold_boundary(self):
        """临近到期：距离下次校准刚好30天（阈值边界）"""
        from unittest.mock import patch
        with patch('api.services.get_instrument_next_calibration_date') as mock_next:
            mock_next.return_value = datetime.now() + timedelta(days=WARNING_APPROACHING_DAYS)
            level = get_warning_level(self.instrument_id)
            self.assertEqual(level, 'approaching')

    def test_normal_beyond_threshold(self):
        """正常：距离下次校准还有60天（超过阈值）"""
        from unittest.mock import patch
        with patch('api.services.get_instrument_next_calibration_date') as mock_next:
            mock_next.return_value = datetime.now() + timedelta(days=60)
            level = get_warning_level(self.instrument_id)
            self.assertIsNone(level)

    def test_no_next_date_returns_none(self):
        """无下次校准日期时返回 None"""
        from unittest.mock import patch
        with patch('api.services.get_instrument_next_calibration_date') as mock_next:
            mock_next.return_value = None
            level = get_warning_level(self.instrument_id)
            self.assertIsNone(level)


class WarningDetectionTest(TestCase):
    """测试预警检测功能"""

    @classmethod
    def setUpTestData(cls):
        calibration_warnings_table.truncate()

    def test_detection_generates_warnings(self):
        """运行预警检测应该生成预警记录"""
        before_count = len(calibration_warnings_table.all())
        generated = run_warning_detection()
        after_count = len(calibration_warnings_table.all())

        self.assertGreater(after_count, before_count)
        self.assertGreater(len(generated), 0)
        for w in generated:
            self.assertIn('level', w)
            self.assertIn(w['level'], ['approaching', 'expired', 'overdue'])
            self.assertEqual(w['status'], 'unhandled')

    def test_detection_idempotent_same_day(self):
        """同一天重复检测不会生成重复预警"""
        run_warning_detection()
        first_count = len(calibration_warnings_table.all())

        run_warning_detection()
        second_count = len(calibration_warnings_table.all())

        self.assertEqual(first_count, second_count)

    def test_detection_updates_level(self):
        """预警级别变更时检测会更新级别"""
        from unittest.mock import patch

        with patch('api.services.get_warning_level') as mock_level:
            mock_level.return_value = 'approaching'
            run_warning_detection()

            first_warnings = calibration_warnings_table.all()
            approaching_count = len([w for w in first_warnings if w.get('level') == 'approaching'])
            self.assertGreater(approaching_count, 0)

        with patch('api.services.get_warning_level') as mock_level:
            mock_level.return_value = 'overdue'
            run_warning_detection()

            updated_warnings = calibration_warnings_table.all()
            overdue_count = len([w for w in updated_warnings if w.get('level') == 'overdue'])
            self.assertGreater(overdue_count, 0)


class WarningListAndFilterTest(TestCase):
    """测试预警列表与筛选功能"""

    @classmethod
    def setUpTestData(cls):
        calibration_warnings_table.truncate()
        run_warning_detection()

    def test_list_returns_list(self):
        """预警列表应返回列表"""
        result = list_warnings()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_list_contains_full_info(self):
        """预警列表项应包含完整信息"""
        result = list_warnings()
        item = result[0]
        self.assertIn('instrument', item)
        self.assertIn('level_label', item)
        self.assertIn('status_label', item)
        self.assertIn('next_calibration_date', item)
        self.assertIn('has_unfinished_flow', item)

    def test_filter_by_level_overdue(self):
        """按超期级别筛选"""
        result = list_warnings(level='overdue')
        for w in result:
            self.assertEqual(w['level'], 'overdue')

    def test_filter_by_level_approaching(self):
        """按临近到期级别筛选"""
        result = list_warnings(level='approaching')
        for w in result:
            self.assertEqual(w['level'], 'approaching')

    def test_filter_by_status_unhandled(self):
        """按未处理状态筛选"""
        result = list_warnings(status='unhandled')
        for w in result:
            self.assertEqual(w['status'], 'unhandled')

    def test_filter_combined(self):
        """组合筛选：级别+状态"""
        result = list_warnings(level='overdue', status='unhandled')
        for w in result:
            self.assertEqual(w['level'], 'overdue')
            self.assertEqual(w['status'], 'unhandled')

    def test_sorted_by_severity(self):
        """预警列表应按严重程度排序：超期 > 已到期 > 临近到期"""
        result = list_warnings()
        levels = [w['level'] for w in result]
        priority = {'overdue': 0, 'expired': 1, 'approaching': 2}
        priorities = [priority.get(l, 3) for l in levels]
        self.assertEqual(priorities, sorted(priorities))


class WarningDetailTest(TestCase):
    """测试预警详情功能"""

    @classmethod
    def setUpTestData(cls):
        calibration_warnings_table.truncate()
        run_warning_detection()
        warnings = calibration_warnings_table.all()
        cls.warning_id = warnings[0].get('id') if warnings else None

    def test_detail_returns_full_info(self):
        """预警详情应包含完整关联信息"""
        if not self.warning_id:
            self.skipTest('No warning records available')

        detail = get_warning_full_info(self.warning_id)
        self.assertIsNotNone(detail)
        self.assertIn('instrument', detail)
        self.assertIn('category', detail)
        self.assertIn('region', detail)
        self.assertIn('responsible_person', detail)
        self.assertIn('rule', detail)
        self.assertIn('level_label', detail)
        self.assertIn('status_label', detail)
        self.assertIn('last_calibration_date', detail)
        self.assertIn('next_calibration_date', detail)

    def test_detail_nonexistent_returns_none(self):
        """不存在的预警ID返回None"""
        detail = get_warning_full_info(99999)
        self.assertIsNone(detail)

    def test_level_label_matches_level(self):
        """级别标签应与级别对应"""
        if not self.warning_id:
            self.skipTest('No warning records available')

        detail = get_warning_full_info(self.warning_id)
        label_map = {
            'approaching': '临近到期',
            'expired': '已到期',
            'overdue': '超期未处理'
        }
        self.assertEqual(detail['level_label'], label_map.get(detail['level']))

    def test_status_label_matches_status(self):
        """状态标签应与状态对应"""
        if not self.warning_id:
            self.skipTest('No warning records available')

        detail = get_warning_full_info(self.warning_id)
        label_map = {
            'unhandled': '未处理',
            'processing': '处理中',
            'handled': '已处理'
        }
        self.assertEqual(detail['status_label'], label_map.get(detail['status']))


class WarningCreateAppointmentTest(TestCase):
    """测试从预警快速发起续检申请"""

    @classmethod
    def setUpTestData(cls):
        calibration_warnings_table.truncate()
        calibration_appointments_table.truncate()
        run_warning_detection()

    def _get_available_warning(self):
        warnings = calibration_warnings_table.search(
            CalibrationWarningQuery.status == 'unhandled'
        )
        for w in warnings:
            if not has_unfinished_flow(w.get('instrument_id')):
                return w
        return None

    def test_create_appointment_success(self):
        """实验员成功发起续检申请"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning, '应有可用的预警')

        appointment, error = create_warning_appointment(
            warning_id=warning.get('id'),
            username='exp01',
            purpose='测试续检申请目的'
        )

        self.assertIsNone(error)
        self.assertIsNotNone(appointment)
        self.assertEqual(appointment.get('from_warning'), True)
        self.assertEqual(appointment.get('warning_id'), warning.get('id'))
        self.assertEqual(appointment.get('status'), 'pending_submit')
        self.assertEqual(appointment.get('instrument_id'), warning.get('instrument_id'))

    def test_create_updates_warning_status(self):
        """发起申请后预警状态变为处理中"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        create_warning_appointment(
            warning_id=warning.get('id'),
            username='exp01',
            purpose='测试更新状态'
        )

        updated = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning.get('id')
        )
        self.assertEqual(updated.get('status'), 'processing')
        self.assertIsNotNone(updated.get('appointment_id'))

    def test_create_handled_warning_fails(self):
        """已处理的预警不能再发起申请"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        w_data = {**warning, 'status': 'handled'}
        calibration_warnings_table.update(w_data, doc_ids=[warning.doc_id])

        appointment, error = create_warning_appointment(
            warning_id=warning.get('id'),
            username='exp01',
            purpose='测试已处理预警'
        )

        self.assertIsNotNone(error)
        self.assertIsNone(appointment)

    def test_create_nonexistent_warning_fails(self):
        """不存在的预警ID应返回错误"""
        appointment, error = create_warning_appointment(
            warning_id=99999,
            username='exp01',
            purpose='不存在的预警'
        )

        self.assertIsNotNone(error)
        self.assertIsNone(appointment)

    def test_create_duplicate_blocked(self):
        """仪器有未完结流程时拦截重复申请"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        appointment1, error1 = create_warning_appointment(
            warning_id=warning.get('id'),
            username='exp01',
            purpose='第一次申请'
        )
        self.assertIsNone(error1)

        warning2 = self._get_available_warning()
        if warning2:
            appointment2, error2 = create_warning_appointment(
                warning_id=warning2.get('id'),
                username='exp02',
                purpose='重复申请测试'
            )
            if warning2.get('instrument_id') == warning.get('instrument_id'):
                self.assertIsNotNone(error2)
                self.assertIn('未完结', error2)


class WarningStatusSyncTest(TestCase):
    """测试预警状态与预约流程的同步"""

    @classmethod
    def setUpTestData(cls):
        calibration_warnings_table.truncate()
        calibration_appointments_table.truncate()
        run_warning_detection()

    def _get_available_warning(self):
        warnings = calibration_warnings_table.search(
            CalibrationWarningQuery.status == 'unhandled'
        )
        for w in warnings:
            if not has_unfinished_flow(w.get('instrument_id')):
                return w
        return None

    def test_submit_changes_to_processing(self):
        """提交审核后预警状态保持处理中"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        appointment, error = create_warning_appointment(
            warning_id=warning.get('id'),
            username='exp01',
            purpose='状态同步测试'
        )
        self.assertIsNone(error)

        apt_id = appointment.get('id')
        apt_doc = calibration_appointments_table.get(
            CalibrationAppointmentQuery.id == apt_id
        )
        apt_data = {**apt_doc, 'status': 'pending_audit'}
        calibration_appointments_table.update(apt_data, doc_ids=[apt_doc.doc_id])

        update_warning_status_from_appointment(apt_id)

        updated = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning.get('id')
        )
        self.assertEqual(updated.get('status'), 'processing')

    def test_closed_changes_to_handled(self):
        """流程结案后预警状态变为已处理"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        appointment, error = create_warning_appointment(
            warning_id=warning.get('id'),
            username='exp01',
            purpose='结案测试'
        )
        self.assertIsNone(error)

        apt_id = appointment.get('id')
        apt_doc = calibration_appointments_table.get(
            CalibrationAppointmentQuery.id == apt_id
        )
        apt_data = {**apt_doc, 'status': 'closed'}
        calibration_appointments_table.update(apt_data, doc_ids=[apt_doc.doc_id])

        update_warning_status_from_appointment(apt_id)

        updated = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning.get('id')
        )
        self.assertEqual(updated.get('status'), 'handled')

    def test_rejected_resets_to_unhandled(self):
        """审核驳回后预警状态回退为未处理"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        appointment, error = create_warning_appointment(
            warning_id=warning.get('id'),
            username='exp01',
            purpose='驳回测试'
        )
        self.assertIsNone(error)

        apt_id = appointment.get('id')
        apt_doc = calibration_appointments_table.get(
            CalibrationAppointmentQuery.id == apt_id
        )

        apt_data1 = {**apt_doc, 'status': 'pending_audit'}
        calibration_appointments_table.update(apt_data1, doc_ids=[apt_doc.doc_id])

        apt_doc2 = calibration_appointments_table.get(
            CalibrationAppointmentQuery.id == apt_id
        )
        apt_data2 = {**apt_doc2, 'status': 'rejected'}
        calibration_appointments_table.update(apt_data2, doc_ids=[apt_doc2.doc_id])

        update_warning_status_from_appointment(apt_id)

        updated = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning.get('id')
        )
        self.assertEqual(updated.get('status'), 'unhandled')

    def test_reset_by_id_from_processing(self):
        """reset_warning_status_by_id 能将处理中的预警重置为未处理"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        w_data = {**warning, 'status': 'processing', 'appointment_id': 999}
        calibration_warnings_table.update(w_data, doc_ids=[warning.doc_id])

        reset_warning_status_by_id(warning.get('id'))

        updated = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning.get('id')
        )
        self.assertEqual(updated.get('status'), 'unhandled')
        self.assertIsNone(updated.get('appointment_id'))

    def test_reset_by_id_handled_stays_handled(self):
        """reset_warning_status_by_id 不应改变已处理状态"""
        warning = self._get_available_warning()
        self.assertIsNotNone(warning)

        w_data = {**warning, 'status': 'handled', 'appointment_id': 999}
        calibration_warnings_table.update(w_data, doc_ids=[warning.doc_id])

        reset_warning_status_by_id(warning.get('id'))

        updated = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning.get('id')
        )
        self.assertEqual(updated.get('status'), 'handled')


class WarningDashboardTest(TestCase):
    """测试预警汇总看板"""

    @classmethod
    def setUpTestData(cls):
        calibration_warnings_table.truncate()
        run_warning_detection()

    def test_dashboard_has_summary(self):
        """看板应包含汇总数据"""
        dashboard = get_warning_dashboard()
        self.assertIn('summary', dashboard)
        summary = dashboard['summary']

        for key in ['total', 'approaching', 'expired', 'overdue',
                    'unhandled', 'processing', 'handled']:
            self.assertIn(key, summary)

    def test_summary_total_equals_levels_sum(self):
        """汇总总数应等于各级别之和"""
        dashboard = get_warning_dashboard()
        summary = dashboard['summary']
        level_sum = summary['approaching'] + summary['expired'] + summary['overdue']
        self.assertEqual(summary['total'], level_sum)

    def test_summary_total_equals_statuses_sum(self):
        """汇总总数应等于各状态之和"""
        dashboard = get_warning_dashboard()
        summary = dashboard['summary']
        status_sum = summary['unhandled'] + summary['processing'] + summary['handled']
        self.assertEqual(summary['total'], status_sum)

    def test_dashboard_has_by_region(self):
        """看板应包含按区域统计"""
        dashboard = get_warning_dashboard()
        self.assertIn('by_region', dashboard)
        self.assertIsInstance(dashboard['by_region'], dict)

    def test_dashboard_has_by_category(self):
        """看板应包含按类别统计"""
        dashboard = get_warning_dashboard()
        self.assertIn('by_category', dashboard)
        self.assertIsInstance(dashboard['by_category'], dict)

    def test_dashboard_has_by_responsible_person(self):
        """看板应包含按责任人统计"""
        dashboard = get_warning_dashboard()
        self.assertIn('by_responsible_person', dashboard)
        self.assertIsInstance(dashboard['by_responsible_person'], dict)

    def test_dimension_stats_have_all_keys(self):
        """各维度统计应包含所有级别和状态键"""
        dashboard = get_warning_dashboard()
        expected_keys = ['total', 'approaching', 'expired', 'overdue',
                         'unhandled', 'processing', 'handled']

        for dim_name in ['by_region', 'by_category', 'by_responsible_person']:
            dim = dashboard[dim_name]
            for name, stats in dim.items():
                for key in expected_keys:
                    self.assertIn(key, stats, f'{dim_name}/{name} 缺少 {key}')

    def test_dimension_totals_match(self):
        """各维度的总数应与汇总总数一致"""
        dashboard = get_warning_dashboard()
        summary = dashboard['summary']

        for dim_name in ['by_region', 'by_category', 'by_responsible_person']:
            dim = dashboard[dim_name]
            dim_total = sum(stats['total'] for stats in dim.values())
            self.assertEqual(dim_total, summary['total'],
                             f'{dim_name} 总数与汇总不一致')


class WarningAPIPermissionTest(TestCase):
    """测试预警模块 API 权限控制"""

    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        calibration_warnings_table.truncate()
        run_warning_detection()

    def _auth_headers(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_warning_list_authenticated_access(self):
        """所有登录角色都应能访问预警列表"""
        roles = ['admin', 'exp01', 'audit01', 'cali01']
        for role in roles:
            token = get_token_for_user(role)
            response = self.client.get('/api/warnings/', **self._auth_headers(token))
            self.assertEqual(response.status_code, 200,
                             f'{role} 应能访问预警列表')

    def test_warning_list_unauthenticated_denied(self):
        """未登录用户不能访问预警列表"""
        response = self.client.get('/api/warnings/')
        self.assertEqual(response.status_code, 401)

    def test_warning_dashboard_admin_only(self):
        """只有管理员能访问看板"""
        admin_token = get_token_for_user('admin')
        exp_token = get_token_for_user('exp01')
        audit_token = get_token_for_user('audit01')
        cali_token = get_token_for_user('cali01')

        response = self.client.get('/api/warnings/dashboard/', **self._auth_headers(admin_token))
        self.assertEqual(response.status_code, 200)

        for token, role in [(exp_token, 'exp01'), (audit_token, 'audit01'), (cali_token, 'cali01')]:
            response = self.client.get('/api/warnings/dashboard/', **self._auth_headers(token))
            self.assertEqual(response.status_code, 403, f'{role} 不应访问看板')

    def test_create_appointment_experimenter_only(self):
        """只有实验员能发起续检申请"""
        warnings = calibration_warnings_table.search(
            CalibrationWarningQuery.status == 'unhandled'
        )
        self.assertGreater(len(warnings), 0)
        warning_id = warnings[0].get('id')

        admin_token = get_token_for_user('admin')
        audit_token = get_token_for_user('audit01')
        cali_token = get_token_for_user('cali01')

        for token, role in [(admin_token, 'admin'), (audit_token, 'audit01'), (cali_token, 'cali01')]:
            response = self.client.post(
                '/api/warnings/create-appointment/',
                data=json.dumps({'warning_id': warning_id, 'purpose': '权限测试'}),
                content_type='application/json',
                **self._auth_headers(token)
            )
            self.assertEqual(response.status_code, 403, f'{role} 不应发起续检申请')

    def test_detect_admin_only(self):
        """只有管理员能触发预警检测"""
        exp_token = get_token_for_user('exp01')
        response = self.client.post('/api/warnings/detect/', **self._auth_headers(exp_token))
        self.assertEqual(response.status_code, 403)

        admin_token = get_token_for_user('admin')
        response = self.client.post('/api/warnings/detect/', **self._auth_headers(admin_token))
        self.assertEqual(response.status_code, 200)


class WarningAPIIntegrationTest(TestCase):
    """预警模块 API 集成测试"""

    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        calibration_warnings_table.truncate()
        calibration_appointments_table.truncate()
        run_warning_detection()

    def _auth_headers(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def test_warning_list_api(self):
        """测试预警列表 API"""
        token = get_token_for_user('admin')
        response = self.client.get('/api/warnings/', **self._auth_headers(token))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_warning_detail_api(self):
        """测试预警详情 API"""
        token = get_token_for_user('admin')
        warnings = calibration_warnings_table.all()
        self.assertGreater(len(warnings), 0)
        warning_id = warnings[0].get('id')

        response = self.client.get(
            f'/api/warnings/{warning_id}/',
            **self._auth_headers(token)
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['id'], warning_id)
        self.assertIn('instrument', data)

    def test_warning_filter_api(self):
        """测试预警筛选 API"""
        token = get_token_for_user('admin')
        response = self.client.get(
            '/api/warnings/?level=overdue&status=unhandled',
            **self._auth_headers(token)
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        for item in data:
            self.assertEqual(item['level'], 'overdue')
            self.assertEqual(item['status'], 'unhandled')

    def test_create_appointment_api(self):
        """测试快速发起续检申请 API"""
        exp_token = get_token_for_user('exp01')

        warnings = calibration_warnings_table.search(
            CalibrationWarningQuery.status == 'unhandled'
        )
        target = None
        for w in warnings:
            if not has_unfinished_flow(w.get('instrument_id')):
                target = w
                break
        self.assertIsNotNone(target)

        response = self.client.post(
            '/api/warnings/create-appointment/',
            data=json.dumps({
                'warning_id': target.get('id'),
                'purpose': 'API集成测试-续检申请'
            }),
            content_type='application/json',
            **self._auth_headers(exp_token)
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertIn('appointment', data)
        self.assertEqual(data['appointment']['from_warning'], True)
        self.assertEqual(data['appointment']['warning_id'], target.get('id'))

    def test_dashboard_api(self):
        """测试预警看板 API"""
        token = get_token_for_user('admin')
        response = self.client.get('/api/warnings/dashboard/', **self._auth_headers(token))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('summary', data)
        self.assertIn('by_region', data)
        self.assertIn('by_category', data)
        self.assertIn('by_responsible_person', data)

    def test_detect_api(self):
        """测试预警检测 API"""
        token = get_token_for_user('admin')
        response = self.client.post('/api/warnings/detect/', **self._auth_headers(token))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('generated_count', data)
        self.assertIn('warnings', data)

    def test_appointment_detail_shows_warning_flag(self):
        """预约详情应显示预警来源标记"""
        exp_token = get_token_for_user('exp01')

        warnings = calibration_warnings_table.search(
            CalibrationWarningQuery.status == 'unhandled'
        )
        target = None
        for w in warnings:
            if not has_unfinished_flow(w.get('instrument_id')):
                target = w
                break
        self.assertIsNotNone(target)

        create_resp = self.client.post(
            '/api/warnings/create-appointment/',
            data=json.dumps({
                'warning_id': target.get('id'),
                'purpose': '详情标记测试'
            }),
            content_type='application/json',
            **self._auth_headers(exp_token)
        )
        apt_id = json.loads(create_resp.content)['appointment']['id']

        detail_resp = self.client.get(
            f'/api/appointments/{apt_id}/',
            **self._auth_headers(exp_token)
        )
        detail_data = json.loads(detail_resp.content)
        self.assertTrue(detail_data.get('from_warning'))
        self.assertEqual(detail_data.get('warning_id'), target.get('id'))

    def test_delete_draft_resets_warning(self):
        """删除草稿后预警状态回退为未处理"""
        exp_token = get_token_for_user('exp01')

        warnings = calibration_warnings_table.search(
            CalibrationWarningQuery.status == 'unhandled'
        )
        target = None
        for w in warnings:
            if not has_unfinished_flow(w.get('instrument_id')):
                target = w
                break
        self.assertIsNotNone(target)
        warning_id = target.get('id')

        create_resp = self.client.post(
            '/api/warnings/create-appointment/',
            data=json.dumps({
                'warning_id': warning_id,
                'purpose': '删除草稿测试'
            }),
            content_type='application/json',
            **self._auth_headers(exp_token)
        )
        apt_id = json.loads(create_resp.content)['appointment']['id']

        before_warning = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning_id
        )
        self.assertEqual(before_warning.get('status'), 'processing')

        self.client.delete(
            f'/api/appointments/{apt_id}/',
            **self._auth_headers(exp_token)
        )

        after_warning = calibration_warnings_table.get(
            CalibrationWarningQuery.id == warning_id
        )
        self.assertEqual(after_warning.get('status'), 'unhandled')
        self.assertIsNone(after_warning.get('appointment_id'))


class HasUnfinishedFlowTest(TestCase):
    """测试未完结流程检查"""

    @classmethod
    def setUpTestData(cls):
        cls.instrument_id = 99
        calibration_appointments_table.truncate()

    def test_no_appointments_returns_false(self):
        """无预约时返回False"""
        result = has_unfinished_flow(self.instrument_id)
        self.assertFalse(result)

    def test_only_closed_appointments_returns_false(self):
        """只有已结案预约时返回False"""
        from api.database import generate_id, now_str
        apt_data = {
            'id': generate_id(calibration_appointments_table),
            'appointment_no': 'TEST001',
            'instrument_id': self.instrument_id,
            'applicant': '测试员',
            'department': '测试部',
            'purpose': '测试',
            'expected_date': '2025-01-01',
            'status': 'closed',
            'has_precheck': False,
            'precheck_id': None,
            'remark': '',
            'created_at': now_str(),
            'submitted_at': None,
            'from_warning': False,
            'warning_id': None
        }
        calibration_appointments_table.insert(apt_data)
        result = has_unfinished_flow(self.instrument_id)
        self.assertFalse(result)

    def test_pending_appointment_returns_true(self):
        """有待处理预约时返回True"""
        from api.database import generate_id, now_str
        pending_statuses = [
            'pending_submit', 'pending_audit', 'pending_calibration',
            'calibrating', 'pending_acceptance', 'deviation_pending'
        ]
        for i, status in enumerate(pending_statuses):
            inst_id = 100 + i
            apt_data = {
                'id': generate_id(calibration_appointments_table),
                'appointment_no': f'TEST{100+i:03d}',
                'instrument_id': inst_id,
                'applicant': '测试员',
                'department': '测试部',
                'purpose': '测试',
                'expected_date': '2025-01-01',
                'status': status,
                'has_precheck': False,
                'precheck_id': None,
                'remark': '',
                'created_at': now_str(),
                'submitted_at': None,
                'from_warning': False,
                'warning_id': None
            }
            calibration_appointments_table.insert(apt_data)
            result = has_unfinished_flow(inst_id)
            self.assertTrue(result, f'{status} 状态应被视为未完结')
