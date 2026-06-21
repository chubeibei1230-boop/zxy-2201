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
    now_str
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
        'warnings': []
    }
    if check_audit_timeout(appointment_id):
        result['warnings'].append('审核超时')
    if check_precheck_missing(appointment_id):
        result['warnings'].append('前置检查缺失')
    return result
