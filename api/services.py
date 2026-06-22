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
    elif diff_days <= WARNING_APPROACHING_DAYS:
        return 'approaching' if diff_days >= 0 else 'expired'
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
