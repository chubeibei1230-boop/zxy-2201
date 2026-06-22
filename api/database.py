from tinydb import TinyDB, Query
from django.conf import settings
import os
from datetime import datetime

os.makedirs(os.path.dirname(settings.TINYDB_PATH), exist_ok=True)

db = TinyDB(settings.TINYDB_PATH, indent=2, ensure_ascii=False)

users_table = db.table('users')
instrument_categories_table = db.table('instrument_categories')
instruments_table = db.table('instruments')
experiment_regions_table = db.table('experiment_regions')
calibration_rules_table = db.table('calibration_rules')
storage_locations_table = db.table('storage_locations')
responsible_persons_table = db.table('responsible_persons')
calibration_appointments_table = db.table('calibration_appointments')
precheck_records_table = db.table('precheck_records')
audit_records_table = db.table('audit_records')
calibration_records_table = db.table('calibration_records')
acceptance_records_table = db.table('acceptance_records')
calibration_warnings_table = db.table('calibration_warnings')
anomaly_tasks_table = db.table('anomaly_tasks')
anomaly_process_records_table = db.table('anomaly_process_records')
change_requests_table = db.table('change_requests')
change_audit_records_table = db.table('change_audit_records')

UserQuery = Query()
InstrumentCategoryQuery = Query()
InstrumentQuery = Query()
ExperimentRegionQuery = Query()
CalibrationRuleQuery = Query()
StorageLocationQuery = Query()
ResponsiblePersonQuery = Query()
CalibrationAppointmentQuery = Query()
PrecheckRecordQuery = Query()
AuditRecordQuery = Query()
CalibrationRecordQuery = Query()
AcceptanceRecordQuery = Query()
CalibrationWarningQuery = Query()
AnomalyTaskQuery = Query()
AnomalyProcessRecordQuery = Query()
ChangeRequestQuery = Query()
ChangeAuditRecordQuery = Query()


def generate_id(table):
    records = table.all()
    if not records:
        return 1
    return max(r.get('id', 0) for r in records) + 1


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def today_str():
    return datetime.now().strftime('%Y-%m-%d')
