from datetime import datetime, timedelta
from django.conf import settings
from .database import (
    calibration_appointments_table as apt_table,
    instruments_table as inst_table,
    calibration_records_table as cr_table,
    precheck_records_table,
    audit_records_table,
    experiment_regions_table,
    instrument_categories_table,
    storage_locations_table,
    responsible_persons_table,
    calibration_rules_table,
    acceptance_records_table,
    calibration_warnings_table,
    anomaly_tasks_table,
    anomaly_process_records_table,
    users_table,
    CalibrationAppointmentQuery,
    InstrumentQuery,
    CalibrationRecordQuery,
    AuditRecordQuery,
    AcceptanceRecordQuery,
    InstrumentCategoryQuery,
    ExperimentRegionQuery,
    StorageLocationQuery,
    ResponsiblePersonQuery,
    CalibrationRuleQuery,
    PrecheckRecordQuery,
    CalibrationWarningQuery,
    AnomalyTaskQuery,
    AnomalyProcessRecordQuery,
    UserQuery,
    now_str, today_str, generate_id
)


def check_duplicate_calibration(instrument_id, expected_date, exclude_appointment_id=None):
    appointments = apt_table.search(
        (CalibrationAppointmentQuery.instrument_id == instrument_id) &
        (CalibrationAppointmentQuery.expected_date == expected_date) &
        (CalibrationAppointmentQuery.status.one_of([
            'pending_submit', 'pending_audit', 'pending_calibration',
            'calibrating', 'pending_acceptance', 'deviation_pending'
        ]))
    )
    if exclude_appointment_id:
        appointments = [a for a in appointments if a.get('id') != exclude_appointment_id]
    return len(appointments) > 0


def check_audit_timeout(appointment_id):
    apt = apt_table.get(CalibrationAppointmentQuery.id == appointment_id)
    if not apt or apt.get('status') != 'pending_audit':
        return False
    submitted_at = apt.get('submitted_at')
    if not submitted_at:
        return False
    try:
        submit_time = datetime.strptime(submitted_at, '%Y-%m-%d %H:%M:%S')
        days_passed = (datetime.now() - submit_time).days
        return days_passed > settings.AUDIT_TIMEOUT_DAYS
    except:
        return False


def check_precheck_missing(appointment_id):
    apt = apt_table.get(CalibrationAppointmentQuery.id == appointment_id)
    if not apt or apt.get('status') != 'pending_calibration':
        return False
    if apt.get('has_precheck') and apt.get('precheck_id'):
        precheck = precheck_records_table.get(PrecheckRecordQuery.id == apt['precheck_id'])
        if precheck:
            return False
    created_at = apt.get('created_at')
    if not created_at:
        return True
    try:
        create_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        days_passed = (datetime.now() - create_time).days
        return days_passed > settings.PRECHECK_TIMEOUT_DAYS
    except:
        return True


def check_region_deviation_concentration():
    warnings = []
    all_records = cr_table.search(
        CalibrationRecordQuery.deviation_level.one_of(['minor', 'major', 'critical'])
    )
    region_counts = {}
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    for record in all_records:
        apt = apt_table.get(CalibrationAppointmentQuery.id == record.get('appointment_id'))
        if not apt:
            continue
        inst = inst_table.get(InstrumentQuery.id == apt.get('instrument_id'))
        if not inst:
            continue
        region_id = inst.get('region_id')
        record_date = record.get('created_at', '')[:10]
        if record_date < thirty_days_ago:
            continue
        if region_id not in region_counts:
            region_counts[region_id] = {'count': 0, 'records': []}
        region_counts[region_id]['count'] += 1
        region_counts[region_id]['records'].append(record.get('id'))
    for region_id, data in region_counts.items():
        if data['count'] >= settings.REGION_DEVIATION_THRESHOLD:
            region = experiment_regions_table.get(ExperimentRegionQuery.id == region_id)
            region_name = region.get('name') if region else f'区域{region_id}'
            warnings.append({
                'region_id': region_id,
                'region_name': region_name,
                'deviation_count': data['count'],
                'record_ids': data['records'],
                'warning': f'{region_name}近30天内出现{data["count"]}次偏差，超过阈值{settings.REGION_DEVIATION_THRESHOLD}'
            })
    return warnings


def check_accessory_unclosed():
    warnings = []
    records = cr_table.search(
        (CalibrationRecordQuery.accessory_status.one_of(['damaged', 'missing'])) &
        (CalibrationRecordQuery.closing_remark == '')
    )
    for record in records:
        apt = apt_table.get(CalibrationAppointmentQuery.id == record.get('appointment_id'))
        if apt and apt.get('status') != 'closed':
            inst = inst_table.get(InstrumentQuery.id == apt.get('instrument_id'))
            inst_name = inst.get('name', '') if inst else ''
            warnings.append({
                'record_id': record.get('id'),
                'appointment_id': record.get('appointment_id'),
                'instrument_name': inst_name,
                'accessory_status': record.get('accessory_status'),
                'warning': f'仪器{inst_name}配件{record.get("accessory_status")}未结案处理'
            })
    return warnings


def check_storage_location_conflict():
    warnings = []
    instruments = inst_table.all()
    location_map = {}
    for inst in instruments:
        location_id = inst.get('location_id')
        if not location_id:
            continue
        if location_id not in location_map:
            location_map[location_id] = []
        location_map[location_id].append(inst)
    for location_id, inst_list in location_map.items():
        if len(inst_list) > 1:
            location = storage_locations_table.get(StorageLocationQuery.id == location_id)
            loc_name = location.get('name') if location else f'位置{location_id}'
            warnings.append({
                'location_id': location_id,
                'location_name': loc_name,
                'instrument_count': len(inst_list),
                'instruments': [{'id': i.get('id'), 'name': i.get('name'), 'serial': i.get('serial_number')} for i in inst_list],
                'warning': f'存放位置{loc_name}存在{len(inst_list)}台仪器，可能存在冲突'
            })
    return warnings


def run_all_checks():
    return {
        'audit_timeout': [apt.get('id') for apt in apt_table.all() if check_audit_timeout(apt.get('id'))],
        'precheck_missing': [apt.get('id') for apt in apt_table.all() if check_precheck_missing(apt.get('id'))],
        'region_deviation': check_region_deviation_concentration(),
        'accessory_unclosed': check_accessory_unclosed(),
        'storage_conflict': check_storage_location_conflict(),
        'check_time': now_str()
    }


def get_appointment_full_info(appointment_id):
    apt = apt_table.get(CalibrationAppointmentQuery.id == appointment_id)
    if not apt:
        return None
    inst = inst_table.get(InstrumentQuery.id == apt.get('instrument_id'))
    category = instrument_categories_table.get(InstrumentCategoryQuery.id == inst.get('category_id')) if inst else None
    region = experiment_regions_table.get(ExperimentRegionQuery.id == inst.get('region_id')) if inst else None
    location = storage_locations_table.get(StorageLocationQuery.id == inst.get('location_id')) if inst else None
    person = responsible_persons_table.get(ResponsiblePersonQuery.id == inst.get('responsible_person_id')) if inst else None
    rule = calibration_rules_table.get(CalibrationRuleQuery.id == inst.get('rule_id')) if inst else None
    precheck = precheck_records_table.get(PrecheckRecordQuery.id == apt.get('precheck_id')) if apt.get('precheck_id') else None
    audits = audit_records_table.search(AuditRecordQuery.appointment_id == appointment_id)
    calibrations = cr_table.search(CalibrationRecordQuery.appointment_id == appointment_id)
    acceptances = acceptance_records_table.search(AcceptanceRecordQuery.appointment_id == appointment_id)
    result = {
        **apt,
        'instrument': {**inst} if inst else None,
        'category': {**category} if category else None,
        'region': {**region} if region else None,
        'location': {**location} if location else None,
        'responsible_person': {**person} if person else None,
        'rule': {**rule} if rule else None,
        'precheck': {**precheck} if precheck else None,
        'audits': [{**a} for a in audits],
        'calibrations': [{**c} for c in calibrations],
        'acceptances': [{**a} for a in acceptances],
        'warnings': [],
        'from_warning': apt.get('from_warning', False),
        'warning_id': apt.get('warning_id')
    }
    if check_audit_timeout(appointment_id):
        result['warnings'].append('审核超时')
    if check_precheck_missing(appointment_id):
        result['warnings'].append('前置检查缺失')
    return result


WARNING_APPROACHING_DAYS = 30


def get_instrument_last_calibration_date(instrument_id):
    records = cr_table.search(
        CalibrationRecordQuery.appointment_id.one_of([
            a.get('id') for a in apt_table.search(
                CalibrationAppointmentQuery.instrument_id == instrument_id
            )
        ])
    )
    if not records:
        inst = inst_table.get(InstrumentQuery.id == instrument_id)
        if inst and inst.get('purchase_date'):
            try:
                return datetime.strptime(inst['purchase_date'], '%Y-%m-%d')
            except:
                pass
        return None
    latest = sorted(records, key=lambda r: r.get('end_date', r.get('created_at', '')), reverse=True)[0]
    date_str = latest.get('end_date') or latest.get('created_at', '')
    try:
        return datetime.strptime(date_str[:10], '%Y-%m-%d')
    except:
        return None


def get_instrument_next_calibration_date(instrument_id):
    last_date = get_instrument_last_calibration_date(instrument_id)
    if not last_date:
        return None
    inst = inst_table.get(InstrumentQuery.id == instrument_id)
    if not inst:
        return None
    rule = calibration_rules_table.get(CalibrationRuleQuery.id == inst.get('rule_id'))
    if not rule:
        return None
    cycle_days = rule.get('cycle_days', 365)
    return last_date + timedelta(days=cycle_days)


def get_warning_level(instrument_id):
    next_date = get_instrument_next_calibration_date(instrument_id)
    if not next_date:
        return None
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    diff_days = (next_date - today).days
    if diff_days < 0:
        return 'overdue'
    elif diff_days == 0:
        return 'expired'
    elif diff_days <= WARNING_APPROACHING_DAYS:
        return 'approaching'
    return None


def has_unfinished_flow(instrument_id):
    appointments = apt_table.search(
        (CalibrationAppointmentQuery.instrument_id == instrument_id) &
        (CalibrationAppointmentQuery.status.one_of([
            'pending_submit', 'pending_audit', 'pending_calibration',
            'calibrating', 'pending_acceptance', 'deviation_pending'
        ]))
    )
    return len(appointments) > 0


def get_unfinished_appointment(instrument_id):
    appointments = apt_table.search(
        (CalibrationAppointmentQuery.instrument_id == instrument_id) &
        (CalibrationAppointmentQuery.status.one_of([
            'pending_submit', 'pending_audit', 'pending_calibration',
            'calibrating', 'pending_acceptance', 'deviation_pending'
        ]))
    )
    return appointments[0] if appointments else None


def run_warning_detection():
    today = datetime.now()
    today_str_val = today.strftime('%Y-%m-%d')
    instruments = inst_table.search(InstrumentQuery.status == 'active')

    generated = []
    for inst in instruments:
        level = get_warning_level(inst.get('id'))
        if not level:
            continue

        existing = calibration_warnings_table.search(
            (CalibrationWarningQuery.instrument_id == inst.get('id')) &
            (CalibrationWarningQuery.warning_date == today_str_val)
        )

        if not existing:
            warning_id = generate_id(calibration_warnings_table)
            next_date = get_instrument_next_calibration_date(inst.get('id'))
            warning_data = {
                'id': warning_id,
                'instrument_id': inst.get('id'),
                'level': level,
                'warning_date': today_str_val,
                'next_calibration_date': next_date.strftime('%Y-%m-%d') if next_date else None,
                'status': 'unhandled',
                'appointment_id': None,
                'created_at': now_str()
            }
            calibration_warnings_table.insert(warning_data)
            generated.append(warning_data)
        else:
            for w in existing:
                if w.get('level') != level and w.get('status') != 'handled':
                    update_data = {**w, 'level': level}
                    calibration_warnings_table.update(update_data, doc_ids=[w.doc_id])

    return generated


def get_warning_full_info(warning_id):
    warning = calibration_warnings_table.get(CalibrationWarningQuery.id == int(warning_id))
    if not warning:
        return None

    inst = inst_table.get(InstrumentQuery.id == warning.get('instrument_id'))
    category = instrument_categories_table.get(InstrumentCategoryQuery.id == inst.get('category_id')) if inst else None
    region = experiment_regions_table.get(ExperimentRegionQuery.id == inst.get('region_id')) if inst else None
    location = storage_locations_table.get(StorageLocationQuery.id == inst.get('location_id')) if inst else None
    person = responsible_persons_table.get(ResponsiblePersonQuery.id == inst.get('responsible_person_id')) if inst else None
    rule = calibration_rules_table.get(CalibrationRuleQuery.id == inst.get('rule_id')) if inst else None

    appointment = None
    if warning.get('appointment_id'):
        appointment = apt_table.get(CalibrationAppointmentQuery.id == warning.get('appointment_id'))

    level_label = {
        'approaching': '临近到期',
        'expired': '已到期',
        'overdue': '超期未处理'
    }.get(warning.get('level'), warning.get('level'))

    status_label = {
        'unhandled': '未处理',
        'processing': '处理中',
        'handled': '已处理'
    }.get(warning.get('status'), warning.get('status'))

    last_cal_date = get_instrument_last_calibration_date(warning.get('instrument_id'))

    return {
        **warning,
        'level_label': level_label,
        'status_label': status_label,
        'instrument': {**inst} if inst else None,
        'category': {**category} if category else None,
        'region': {**region} if region else None,
        'location': {**location} if location else None,
        'responsible_person': {**person} if person else None,
        'rule': {**rule} if rule else None,
        'appointment': {**appointment} if appointment else None,
        'last_calibration_date': last_cal_date.strftime('%Y-%m-%d') if last_cal_date else None,
        'has_unfinished_flow': has_unfinished_flow(warning.get('instrument_id'))
    }


def list_warnings(level=None, status=None, region_id=None, category_id=None, responsible_person_id=None):
    run_warning_detection()
    warnings = calibration_warnings_table.all()

    if level:
        warnings = [w for w in warnings if w.get('level') == level]
    if status:
        warnings = [w for w in warnings if w.get('status') == status]
    if region_id:
        region_id = int(region_id)
        filtered = []
        for w in warnings:
            inst = inst_table.get(InstrumentQuery.id == w.get('instrument_id'))
            if inst and inst.get('region_id') == region_id:
                filtered.append(w)
        warnings = filtered
    if category_id:
        category_id = int(category_id)
        filtered = []
        for w in warnings:
            inst = inst_table.get(InstrumentQuery.id == w.get('instrument_id'))
            if inst and inst.get('category_id') == category_id:
                filtered.append(w)
        warnings = filtered
    if responsible_person_id:
        responsible_person_id = int(responsible_person_id)
        filtered = []
        for w in warnings:
            inst = inst_table.get(InstrumentQuery.id == w.get('instrument_id'))
            if inst and inst.get('responsible_person_id') == responsible_person_id:
                filtered.append(w)
        warnings = filtered

    result = []
    for w in warnings:
        info = get_warning_full_info(w.get('id'))
        if info:
            result.append(info)

    result.sort(key=lambda x: (
        {'overdue': 0, 'expired': 1, 'approaching': 2}.get(x.get('level'), 3),
        x.get('next_calibration_date', '')
    ))
    return result


def create_warning_appointment(warning_id, username, purpose):
    warning = calibration_warnings_table.get(CalibrationWarningQuery.id == int(warning_id))
    if not warning:
        return None, '预警记录不存在'

    if warning.get('status') == 'handled':
        return None, '该预警已处理完成'

    instrument_id = warning.get('instrument_id')
    if has_unfinished_flow(instrument_id):
        unfinished = get_unfinished_appointment(instrument_id)
        apt_no = unfinished.get('appointment_no', '') if unfinished else ''
        return None, f'该仪器已存在未完结的校准流程（预约号：{apt_no}），请勿重复发起'

    user_record = users_table.get(UserQuery.username == username)
    if not user_record:
        return None, '用户不存在'
    applicant_name = user_record.get('name', username)
    department = user_record.get('department', '')

    expected_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    obj_id = generate_id(apt_table)
    today = datetime.now().strftime('%y%m%d')
    all_appointments = apt_table.all()
    today_appointments = [a for a in all_appointments if a.get('appointment_no', '').startswith(today)]
    seq = len(today_appointments) + 1
    appointment_no = f'{today}{seq:04d}'

    appointment_data = {
        'id': obj_id,
        'appointment_no': appointment_no,
        'instrument_id': instrument_id,
        'applicant': applicant_name,
        'department': department,
        'purpose': purpose,
        'expected_date': expected_date,
        'status': 'pending_submit',
        'has_precheck': False,
        'precheck_id': None,
        'remark': '由到期预警触发的续检申请',
        'created_at': now_str(),
        'submitted_at': None,
        'from_warning': True,
        'warning_id': warning.get('id')
    }
    apt_table.insert(appointment_data)

    warning_update = {
        **warning,
        'status': 'processing',
        'appointment_id': obj_id
    }
    calibration_warnings_table.update(warning_update, doc_ids=[warning.doc_id])

    return appointment_data, None


def get_warning_dashboard():
    run_warning_detection()
    all_warnings = calibration_warnings_table.all()

    summary = {
        'total': len(all_warnings),
        'approaching': len([w for w in all_warnings if w.get('level') == 'approaching']),
        'expired': len([w for w in all_warnings if w.get('level') == 'expired']),
        'overdue': len([w for w in all_warnings if w.get('level') == 'overdue']),
        'unhandled': len([w for w in all_warnings if w.get('status') == 'unhandled']),
        'processing': len([w for w in all_warnings if w.get('status') == 'processing']),
        'handled': len([w for w in all_warnings if w.get('status') == 'handled']),
    }

    by_region = {}
    by_category = {}
    by_responsible = {}

    for w in all_warnings:
        inst = inst_table.get(InstrumentQuery.id == w.get('instrument_id'))
        if not inst:
            continue

        region_id = inst.get('region_id')
        region = experiment_regions_table.get(ExperimentRegionQuery.id == region_id)
        region_name = region.get('name', f'区域{region_id}') if region else f'区域{region_id}'
        if region_name not in by_region:
            by_region[region_name] = {'total': 0, 'approaching': 0, 'expired': 0, 'overdue': 0, 'unhandled': 0, 'processing': 0, 'handled': 0}
        by_region[region_name]['total'] += 1
        by_region[region_name][w.get('level', 'approaching')] += 1
        by_region[region_name][w.get('status', 'unhandled')] += 1

        category_id = inst.get('category_id')
        category = instrument_categories_table.get(InstrumentCategoryQuery.id == category_id)
        category_name = category.get('name', f'类别{category_id}') if category else f'类别{category_id}'
        if category_name not in by_category:
            by_category[category_name] = {'total': 0, 'approaching': 0, 'expired': 0, 'overdue': 0, 'unhandled': 0, 'processing': 0, 'handled': 0}
        by_category[category_name]['total'] += 1
        by_category[category_name][w.get('level', 'approaching')] += 1
        by_category[category_name][w.get('status', 'unhandled')] += 1

        person_id = inst.get('responsible_person_id')
        person = responsible_persons_table.get(ResponsiblePersonQuery.id == person_id)
        person_name = person.get('name', f'责任人{person_id}') if person else f'责任人{person_id}'
        if person_name not in by_responsible:
            by_responsible[person_name] = {'total': 0, 'approaching': 0, 'expired': 0, 'overdue': 0, 'unhandled': 0, 'processing': 0, 'handled': 0}
        by_responsible[person_name]['total'] += 1
        by_responsible[person_name][w.get('level', 'approaching')] += 1
        by_responsible[person_name][w.get('status', 'unhandled')] += 1

    return {
        'summary': summary,
        'by_region': by_region,
        'by_category': by_category,
        'by_responsible_person': by_responsible,
        'generated_at': now_str()
    }


def update_warning_status_from_appointment(appointment_id):
    apt = apt_table.get(CalibrationAppointmentQuery.id == appointment_id)
    if not apt or not apt.get('warning_id'):
        return

    warning = calibration_warnings_table.get(CalibrationWarningQuery.id == apt.get('warning_id'))
    if not warning:
        return

    status = apt.get('status')
    if status == 'closed':
        new_status = 'handled'
    elif status in ['pending_submit', 'rejected']:
        if warning.get('status') == 'processing':
            new_status = 'unhandled'
        else:
            new_status = warning.get('status')
    else:
        new_status = 'processing'

    if new_status != warning.get('status'):
        update_data = {**warning, 'status': new_status}
        if new_status == 'unhandled':
            update_data['appointment_id'] = None
        calibration_warnings_table.update(update_data, doc_ids=[warning.doc_id])


def reset_warning_status_by_id(warning_id):
    warning = calibration_warnings_table.get(CalibrationWarningQuery.id == int(warning_id))
    if not warning:
        return
    if warning.get('status') == 'processing':
        update_data = {
            **warning,
            'status': 'unhandled',
            'appointment_id': None
        }
        calibration_warnings_table.update(update_data, doc_ids=[warning.doc_id])


def generate_anomaly_no():
    today = datetime.now().strftime('%y%m%d')
    all_anomalies = anomaly_tasks_table.all()
    today_anomalies = [a for a in all_anomalies if a.get('anomaly_no', '').startswith('AY' + today)]
    seq = len(today_anomalies) + 1
    return f'AY{today}{seq:04d}'


def create_anomaly_task(appointment_id, anomaly_type, anomaly_level, title, description='',
                        calibration_record_id=None, acceptance_record_id=None, discoverer=''):
    apt = apt_table.get(CalibrationAppointmentQuery.id == int(appointment_id))
    if not apt:
        return None, '校准预约不存在'

    inst = inst_table.get(InstrumentQuery.id == apt.get('instrument_id'))
    if not inst:
        return None, '仪器不存在'

    if calibration_record_id:
        cal_record = cr_table.get(CalibrationRecordQuery.id == int(calibration_record_id))
        if not cal_record:
            return None, '校准记录不存在'
        if cal_record.get('appointment_id') != int(appointment_id):
            return None, '校准记录不属于该预约'

    if acceptance_record_id:
        acc_record = acceptance_records_table.get(AcceptanceRecordQuery.id == int(acceptance_record_id))
        if not acc_record:
            return None, '验收记录不存在'
        if acc_record.get('appointment_id') != int(appointment_id):
            return None, '验收记录不属于该预约'

    existing = anomaly_tasks_table.search(
        (AnomalyTaskQuery.appointment_id == int(appointment_id)) &
        (AnomalyTaskQuery.anomaly_type == anomaly_type) &
        (AnomalyTaskQuery.status.one_of(['registered', 'analyzing', 'rectifying', 'reviewing']))
    )
    if existing:
        anomaly = existing[0]
        need_update = False
        update_data = {**anomaly}
        if acceptance_record_id and anomaly.get('acceptance_record_id') != acceptance_record_id:
            update_data['acceptance_record_id'] = acceptance_record_id
            need_update = True
        if calibration_record_id and not anomaly.get('calibration_record_id'):
            update_data['calibration_record_id'] = calibration_record_id
            need_update = True
        if description and not anomaly.get('description'):
            update_data['description'] = description
            need_update = True
        if need_update:
            anomaly_tasks_table.update(update_data, doc_ids=[anomaly.doc_id])
            return get_anomaly_full_info(anomaly.get('id')), None
        return anomaly, None

    anomaly_id = generate_id(anomaly_tasks_table)
    anomaly_no = generate_anomaly_no()

    anomaly_data = {
        'id': anomaly_id,
        'anomaly_no': anomaly_no,
        'appointment_id': int(appointment_id),
        'instrument_id': apt.get('instrument_id'),
        'calibration_record_id': calibration_record_id,
        'acceptance_record_id': acceptance_record_id,
        'anomaly_type': anomaly_type,
        'anomaly_level': anomaly_level,
        'title': title,
        'description': description,
        'status': 'registered',
        'responsible_person_id': inst.get('responsible_person_id'),
        'discoverer': discoverer,
        'discovered_at': now_str(),
        'closed_at': None,
        'created_at': now_str()
    }
    anomaly_tasks_table.insert(anomaly_data)

    record_id = generate_id(anomaly_process_records_table)
    process_record = {
        'id': record_id,
        'anomaly_task_id': anomaly_id,
        'step': 'register',
        'operator': discoverer or 'system',
        'operator_role': 'system',
        'content': f'异常登记：{title}',
        'result': '已登记',
        'remark': description,
        'operated_at': now_str()
    }
    anomaly_process_records_table.insert(process_record)

    return anomaly_data, None


def auto_create_anomaly_from_calibration(calibration_record_id):
    cal_record = cr_table.get(CalibrationRecordQuery.id == int(calibration_record_id))
    if not cal_record:
        return

    apt = apt_table.get(CalibrationAppointmentQuery.id == cal_record.get('appointment_id'))
    if not apt:
        return

    inst = inst_table.get(InstrumentQuery.id == apt.get('instrument_id'))
    inst_name = inst.get('name', '') if inst else ''

    deviation_level = cal_record.get('deviation_level', 'none')
    accessory_status = cal_record.get('accessory_status', 'normal')

    if deviation_level in ['minor', 'major', 'critical']:
        level_map = {
            'minor': 'minor',
            'major': 'major',
            'critical': 'critical'
        }
        level_label = {
            'minor': '轻微',
            'major': '严重',
            'critical': '重大'
        }
        create_anomaly_task(
            appointment_id=cal_record.get('appointment_id'),
            anomaly_type='deviation',
            anomaly_level=level_map.get(deviation_level, 'minor'),
            title=f'{inst_name}校准结果{level_label.get(deviation_level, "")}偏差',
            description=f'标准值：{cal_record.get("standard_value")}，测量值：{cal_record.get("measured_value")}，误差：{cal_record.get("error_value")}',
            calibration_record_id=cal_record.get('id'),
            discoverer=cal_record.get('calibrator', '')
        )

    if accessory_status == 'damaged':
        create_anomaly_task(
            appointment_id=cal_record.get('appointment_id'),
            anomaly_type='accessory_damaged',
            anomaly_level='major',
            title=f'{inst_name}配件损坏',
            description=cal_record.get('accessory_remark', '配件损坏'),
            calibration_record_id=cal_record.get('id'),
            discoverer=cal_record.get('calibrator', '')
        )

    if accessory_status == 'missing':
        create_anomaly_task(
            appointment_id=cal_record.get('appointment_id'),
            anomaly_type='accessory_missing',
            anomaly_level='major',
            title=f'{inst_name}配件缺失',
            description=cal_record.get('accessory_remark', '配件缺失'),
            calibration_record_id=cal_record.get('id'),
            discoverer=cal_record.get('calibrator', '')
        )


def auto_create_anomaly_from_acceptance(acceptance_record_id):
    acc_record = acceptance_records_table.get(AcceptanceRecordQuery.id == int(acceptance_record_id))
    if not acc_record:
        return

    if acc_record.get('result') == True:
        return

    apt = apt_table.get(CalibrationAppointmentQuery.id == acc_record.get('appointment_id'))
    if not apt:
        return

    inst = inst_table.get(InstrumentQuery.id == apt.get('instrument_id'))
    inst_name = inst.get('name', '') if inst else ''

    create_anomaly_task(
        appointment_id=acc_record.get('appointment_id'),
        anomaly_type='acceptance_failed',
        anomaly_level='major',
        title=f'{inst_name}验收不通过',
        description=acc_record.get('opinion', '验收不通过'),
        acceptance_record_id=acc_record.get('id'),
        discoverer=acc_record.get('acceptor', '')
    )


def get_anomaly_full_info(anomaly_id):
    _aid = _safe_int(anomaly_id)
    if _aid is None:
        return None
    anomaly = anomaly_tasks_table.get(AnomalyTaskQuery.id == _aid)
    if not anomaly:
        return None

    apt = apt_table.get(CalibrationAppointmentQuery.id == anomaly.get('appointment_id'))
    inst = inst_table.get(InstrumentQuery.id == anomaly.get('instrument_id'))
    category = instrument_categories_table.get(InstrumentCategoryQuery.id == inst.get('category_id')) if inst else None
    region = experiment_regions_table.get(ExperimentRegionQuery.id == inst.get('region_id')) if inst else None
    location = storage_locations_table.get(StorageLocationQuery.id == inst.get('location_id')) if inst else None
    person = responsible_persons_table.get(ResponsiblePersonQuery.id == anomaly.get('responsible_person_id')) if anomaly.get('responsible_person_id') else None

    cal_record = None
    if anomaly.get('calibration_record_id'):
        cal_record = cr_table.get(CalibrationRecordQuery.id == anomaly.get('calibration_record_id'))

    acc_record = None
    if anomaly.get('acceptance_record_id'):
        acc_record = acceptance_records_table.get(AcceptanceRecordQuery.id == anomaly.get('acceptance_record_id'))

    process_records = anomaly_process_records_table.search(
        AnomalyProcessRecordQuery.anomaly_task_id == _aid
    )
    process_records.sort(key=lambda x: x.get('operated_at', ''))

    type_label = {
        'deviation': '校准偏差',
        'accessory_damaged': '配件损坏',
        'accessory_missing': '配件缺失',
        'acceptance_failed': '验收不通过'
    }.get(anomaly.get('anomaly_type'), anomaly.get('anomaly_type'))

    level_label = {
        'minor': '轻微',
        'major': '严重',
        'critical': '重大'
    }.get(anomaly.get('anomaly_level'), anomaly.get('anomaly_level'))

    status_label = {
        'registered': '已登记',
        'analyzing': '原因分析中',
        'rectifying': '整改中',
        'reviewing': '复核中',
        'closed': '已结案'
    }.get(anomaly.get('status'), anomaly.get('status'))

    return {
        **anomaly,
        'anomaly_type_label': type_label,
        'anomaly_level_label': level_label,
        'status_label': status_label,
        'appointment': {**apt} if apt else None,
        'instrument': {**inst} if inst else None,
        'category': {**category} if category else None,
        'region': {**region} if region else None,
        'location': {**location} if location else None,
        'responsible_person': {**person} if person else None,
        'calibration_record': {**cal_record} if cal_record else None,
        'acceptance_record': {**acc_record} if acc_record else None,
        'process_records': [{**r} for r in process_records]
    }


def _safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def list_anomaly_tasks(status=None, anomaly_level=None, anomaly_type=None,
                       region_id=None, category_id=None, responsible_person_id=None,
                       instrument_id=None, appointment_id=None):
    anomalies = anomaly_tasks_table.all()

    if status:
        anomalies = [a for a in anomalies if a.get('status') == status]
    if anomaly_level:
        anomalies = [a for a in anomalies if a.get('anomaly_level') == anomaly_level]
    if anomaly_type:
        anomalies = [a for a in anomalies if a.get('anomaly_type') == anomaly_type]
    if instrument_id:
        _iid = _safe_int(instrument_id)
        if _iid is not None:
            anomalies = [a for a in anomalies if a.get('instrument_id') == _iid]
    if appointment_id:
        _aid = _safe_int(appointment_id)
        if _aid is not None:
            anomalies = [a for a in anomalies if a.get('appointment_id') == _aid]

    if region_id:
        _rid = _safe_int(region_id)
        if _rid is not None:
            filtered = []
            for a in anomalies:
                inst = inst_table.get(InstrumentQuery.id == a.get('instrument_id'))
                if inst and inst.get('region_id') == _rid:
                    filtered.append(a)
            anomalies = filtered

    if category_id:
        _cid = _safe_int(category_id)
        if _cid is not None:
            filtered = []
            for a in anomalies:
                inst = inst_table.get(InstrumentQuery.id == a.get('instrument_id'))
                if inst and inst.get('category_id') == _cid:
                    filtered.append(a)
            anomalies = filtered

    if responsible_person_id:
        _rpid = _safe_int(responsible_person_id)
        if _rpid is not None:
            filtered = []
            for a in anomalies:
                inst = inst_table.get(InstrumentQuery.id == a.get('instrument_id'))
                if inst and inst.get('responsible_person_id') == _rpid:
                    filtered.append(a)
            anomalies = filtered

    result = []
    for a in anomalies:
        info = get_anomaly_full_info(a.get('id'))
        if info:
            result.append(info)

    result.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return result


def anomaly_do_analysis(anomaly_id, cause_analysis, root_cause='', operator='', operator_role=''):
    _aid = _safe_int(anomaly_id)
    if _aid is None:
        return None, '异常任务ID无效'
    anomaly = anomaly_tasks_table.get(AnomalyTaskQuery.id == _aid)
    if not anomaly:
        return None, '异常任务不存在'

    if anomaly.get('status') not in ['registered']:
        return None, '当前状态不允许进行原因分析'

    new_status = 'analyzing'
    anomaly_update = {
        **anomaly,
        'status': new_status
    }
    anomaly_tasks_table.update(anomaly_update, doc_ids=[anomaly.doc_id])

    record_id = generate_id(anomaly_process_records_table)
    process_record = {
        'id': record_id,
        'anomaly_task_id': _aid,
        'step': 'analysis',
        'operator': operator,
        'operator_role': operator_role,
        'content': cause_analysis,
        'result': root_cause or '已完成原因分析',
        'remark': root_cause,
        'operated_at': now_str()
    }
    anomaly_process_records_table.insert(process_record)

    return get_anomaly_full_info(_aid), None


def anomaly_do_rectification(anomaly_id, rectification_measures, responsible_person='',
                             completion_deadline=None, operator='', operator_role=''):
    _aid = _safe_int(anomaly_id)
    if _aid is None:
        return None, '异常任务ID无效'
    anomaly = anomaly_tasks_table.get(AnomalyTaskQuery.id == _aid)
    if not anomaly:
        return None, '异常任务不存在'

    if anomaly.get('status') not in ['analyzing']:
        return None, '当前状态不允许进行整改'

    new_status = 'rectifying'
    anomaly_update = {
        **anomaly,
        'status': new_status
    }
    anomaly_tasks_table.update(anomaly_update, doc_ids=[anomaly.doc_id])

    record_id = generate_id(anomaly_process_records_table)
    process_record = {
        'id': record_id,
        'anomaly_task_id': _aid,
        'step': 'rectification',
        'operator': operator,
        'operator_role': operator_role,
        'content': rectification_measures,
        'result': f'责任人：{responsible_person}' if responsible_person else '已制定整改措施',
        'remark': f'完成期限：{completion_deadline}' if completion_deadline else '',
        'operated_at': now_str()
    }
    anomaly_process_records_table.insert(process_record)

    return get_anomaly_full_info(_aid), None


def anomaly_do_review(anomaly_id, review_opinion, review_result, operator='', operator_role=''):
    _aid = _safe_int(anomaly_id)
    if _aid is None:
        return None, '异常任务ID无效'
    anomaly = anomaly_tasks_table.get(AnomalyTaskQuery.id == _aid)
    if not anomaly:
        return None, '异常任务不存在'

    if anomaly.get('status') not in ['rectifying']:
        return None, '当前状态不允许进行复核'

    if review_result == 'pass':
        new_status = 'reviewing'
        result_text = '复核通过'
    elif review_result == 'reject':
        new_status = 'analyzing'
        result_text = '复核退回，需重新分析'
    else:
        return None, '无效的复核结果'

    anomaly_update = {
        **anomaly,
        'status': new_status
    }
    anomaly_tasks_table.update(anomaly_update, doc_ids=[anomaly.doc_id])

    record_id = generate_id(anomaly_process_records_table)
    process_record = {
        'id': record_id,
        'anomaly_task_id': _aid,
        'step': 'review',
        'operator': operator,
        'operator_role': operator_role,
        'content': review_opinion,
        'result': result_text,
        'remark': '',
        'operated_at': now_str()
    }
    anomaly_process_records_table.insert(process_record)

    return get_anomaly_full_info(_aid), None


def anomaly_do_close(anomaly_id, conclusion, closing_remark='', operator='', operator_role=''):
    _aid = _safe_int(anomaly_id)
    if _aid is None:
        return None, '异常任务ID无效'
    anomaly = anomaly_tasks_table.get(AnomalyTaskQuery.id == _aid)
    if not anomaly:
        return None, '异常任务不存在'

    if anomaly.get('status') not in ['reviewing']:
        return None, '当前状态不允许结案'

    new_status = 'closed'
    anomaly_update = {
        **anomaly,
        'status': new_status,
        'closed_at': now_str()
    }
    anomaly_tasks_table.update(anomaly_update, doc_ids=[anomaly.doc_id])

    record_id = generate_id(anomaly_process_records_table)
    process_record = {
        'id': record_id,
        'anomaly_task_id': _aid,
        'step': 'close',
        'operator': operator,
        'operator_role': operator_role,
        'content': conclusion,
        'result': '已结案',
        'remark': closing_remark,
        'operated_at': now_str()
    }
    anomaly_process_records_table.insert(process_record)

    sync_appointment_status_from_anomaly(_aid)

    return get_anomaly_full_info(_aid), None


def sync_appointment_status_from_anomaly(anomaly_id):
    _aid = _safe_int(anomaly_id)
    if _aid is None:
        return
    anomaly = anomaly_tasks_table.get(AnomalyTaskQuery.id == _aid)
    if not anomaly:
        return

    apt_id = anomaly.get('appointment_id')
    if not apt_id:
        return

    apt = apt_table.get(CalibrationAppointmentQuery.id == apt_id)
    if not apt:
        return

    open_anomalies = anomaly_tasks_table.search(
        (AnomalyTaskQuery.appointment_id == apt_id) &
        (AnomalyTaskQuery.status.one_of(['registered', 'analyzing', 'rectifying', 'reviewing']))
    )

    if not open_anomalies:
        if apt.get('status') == 'deviation_pending':
            apt_update = {
                **apt,
                'status': 'pending_acceptance'
            }
            apt_table.update(apt_update, doc_ids=[apt.doc_id])
            update_warning_status_from_appointment(apt_id)


def get_anomaly_dashboard():
    all_anomalies = anomaly_tasks_table.all()

    summary = {
        'total': len(all_anomalies),
        'pending': len([a for a in all_anomalies if a.get('status') in ['registered', 'analyzing', 'rectifying', 'reviewing']]),
        'closed': len([a for a in all_anomalies if a.get('status') == 'closed']),
        'registered': len([a for a in all_anomalies if a.get('status') == 'registered']),
        'analyzing': len([a for a in all_anomalies if a.get('status') == 'analyzing']),
        'rectifying': len([a for a in all_anomalies if a.get('status') == 'rectifying']),
        'reviewing': len([a for a in all_anomalies if a.get('status') == 'reviewing']),
    }

    by_type = {}
    by_level = {}
    by_region = {}
    by_category = {}

    for a in all_anomalies:
        atype = a.get('anomaly_type', 'unknown')
        type_label = {
            'deviation': '校准偏差',
            'accessory_damaged': '配件损坏',
            'accessory_missing': '配件缺失',
            'acceptance_failed': '验收不通过'
        }.get(atype, atype)
        if type_label not in by_type:
            by_type[type_label] = {'total': 0, 'pending': 0, 'closed': 0}
        by_type[type_label]['total'] += 1
        if a.get('status') == 'closed':
            by_type[type_label]['closed'] += 1
        else:
            by_type[type_label]['pending'] += 1

        alevel = a.get('anomaly_level', 'unknown')
        level_label = {
            'minor': '轻微',
            'major': '严重',
            'critical': '重大'
        }.get(alevel, alevel)
        if level_label not in by_level:
            by_level[level_label] = {'total': 0, 'pending': 0, 'closed': 0}
        by_level[level_label]['total'] += 1
        if a.get('status') == 'closed':
            by_level[level_label]['closed'] += 1
        else:
            by_level[level_label]['pending'] += 1

        inst = inst_table.get(InstrumentQuery.id == a.get('instrument_id'))
        if inst:
            region_id = inst.get('region_id')
            region = experiment_regions_table.get(ExperimentRegionQuery.id == region_id)
            region_name = region.get('name', f'区域{region_id}') if region else f'区域{region_id}'
            if region_name not in by_region:
                by_region[region_name] = {'total': 0, 'pending': 0, 'closed': 0, 'minor': 0, 'major': 0, 'critical': 0}
            by_region[region_name]['total'] += 1
            if a.get('status') == 'closed':
                by_region[region_name]['closed'] += 1
            else:
                by_region[region_name]['pending'] += 1
            if alevel in by_region[region_name]:
                by_region[region_name][alevel] += 1

            category_id = inst.get('category_id')
            category = instrument_categories_table.get(InstrumentCategoryQuery.id == category_id)
            category_name = category.get('name', f'类别{category_id}') if category else f'类别{category_id}'
            if category_name not in by_category:
                by_category[category_name] = {'total': 0, 'pending': 0, 'closed': 0, 'minor': 0, 'major': 0, 'critical': 0}
            by_category[category_name]['total'] += 1
            if a.get('status') == 'closed':
                by_category[category_name]['closed'] += 1
            else:
                by_category[category_name]['pending'] += 1
            if alevel in by_category[category_name]:
                by_category[category_name][alevel] += 1

    return {
        'summary': summary,
        'by_type': by_type,
        'by_level': by_level,
        'by_region': by_region,
        'by_category': by_category,
        'generated_at': now_str()
    }


def update_appointment_status_with_anomaly(appointment_id):
    _pid = _safe_int(appointment_id)
    if _pid is None:
        return
    apt = apt_table.get(CalibrationAppointmentQuery.id == _pid)
    if not apt:
        return

    open_anomalies = anomaly_tasks_table.search(
        (AnomalyTaskQuery.appointment_id == _pid) &
        (AnomalyTaskQuery.status.one_of(['registered', 'analyzing', 'rectifying', 'reviewing']))
    )

    if open_anomalies and apt.get('status') == 'pending_acceptance':
        apt_update = {
            **apt,
            'status': 'deviation_pending'
        }
        apt_table.update(apt_update, doc_ids=[apt.doc_id])
        update_warning_status_from_appointment(_pid)
