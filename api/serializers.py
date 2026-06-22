from rest_framework import serializers
from .models import (
    ROLE_CHOICES, STATUS_CHOICES, AUDIT_RESULT_CHOICES,
    DEVIATION_LEVEL_CHOICES, ACCESSORY_STATUS_CHOICES,
    WARNING_LEVEL_CHOICES, WARNING_STATUS_CHOICES,
    ANOMALY_TYPE_CHOICES, ANOMALY_LEVEL_CHOICES,
    ANOMALY_STATUS_CHOICES, ANOMALY_STEP_CHOICES,
    CHANGE_TYPE_CHOICES, CHANGE_STATUS_CHOICES,
    CHANGE_AUDIT_RESULT_CHOICES
)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=50)
    password = serializers.CharField(max_length=128)


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(max_length=50)
    role = serializers.ChoiceField(choices=ROLE_CHOICES)
    name = serializers.CharField(max_length=50, required=False)
    department = serializers.CharField(max_length=100, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    email = serializers.EmailField(required=False)
    created_at = serializers.DateTimeField(read_only=True)

    def validate_username(self, value):
        from .database import users_table, UserQuery
        if users_table.get(UserQuery.username == value):
            raise serializers.ValidationError('用户名已存在')
        return value


class UserUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=False)
    name = serializers.CharField(max_length=50, required=False)
    department = serializers.CharField(max_length=100, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(max_length=128, required=False)


class InstrumentCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    code = serializers.CharField(max_length=50)
    description = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class ExperimentRegionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    code = serializers.CharField(max_length=50)
    department = serializers.CharField(max_length=100, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class StorageLocationSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    code = serializers.CharField(max_length=50)
    building = serializers.CharField(max_length=100, required=False)
    floor = serializers.CharField(max_length=50, required=False)
    room = serializers.CharField(max_length=50, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class ResponsiblePersonSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=50)
    department = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False)
    created_at = serializers.DateTimeField(read_only=True)


class CalibrationRuleSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    instrument_category_id = serializers.IntegerField()
    cycle_days = serializers.IntegerField(min_value=1)
    tolerance = serializers.FloatField(required=False)
    standard_value = serializers.FloatField(required=False)
    unit = serializers.CharField(max_length=20, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class InstrumentSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    serial_number = serializers.CharField(max_length=100)
    name = serializers.CharField(max_length=100)
    category_id = serializers.IntegerField()
    model = serializers.CharField(max_length=100, required=False)
    manufacturer = serializers.CharField(max_length=100, required=False)
    purchase_date = serializers.DateField(required=False)
    region_id = serializers.IntegerField()
    location_id = serializers.IntegerField()
    responsible_person_id = serializers.IntegerField()
    rule_id = serializers.IntegerField()
    status = serializers.CharField(max_length=50, default='active')
    description = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class PrecheckItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    result = serializers.BooleanField()
    remark = serializers.CharField(required=False, allow_blank=True)


class PrecheckRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    appointment_id = serializers.IntegerField()
    experimenter = serializers.CharField(max_length=50)
    check_date = serializers.DateField()
    items = serializers.ListField(child=PrecheckItemSerializer())
    overall_result = serializers.BooleanField()
    remark = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class CalibrationAppointmentSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    appointment_no = serializers.CharField(max_length=50, read_only=True)
    instrument_id = serializers.IntegerField()
    applicant = serializers.CharField(max_length=50)
    department = serializers.CharField(max_length=100)
    purpose = serializers.CharField(max_length=500)
    expected_date = serializers.DateField()
    status = serializers.ChoiceField(choices=STATUS_CHOICES, read_only=True)
    has_precheck = serializers.BooleanField(default=False)
    precheck_id = serializers.IntegerField(required=False, allow_null=True)
    remark = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)
    submitted_at = serializers.DateTimeField(required=False, allow_null=True)


class AppointmentSubmitSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()


class AuditRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    appointment_id = serializers.IntegerField()
    auditor = serializers.CharField(max_length=50)
    result = serializers.ChoiceField(choices=AUDIT_RESULT_CHOICES)
    opinion = serializers.CharField(max_length=500)
    audit_date = serializers.DateTimeField(read_only=True)


class CalibrationRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    appointment_id = serializers.IntegerField()
    calibrator = serializers.CharField(max_length=50)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    standard_value = serializers.FloatField(required=False)
    measured_value = serializers.FloatField(required=False)
    error_value = serializers.FloatField(required=False, read_only=True)
    deviation_level = serializers.ChoiceField(choices=DEVIATION_LEVEL_CHOICES)
    accessory_status = serializers.ChoiceField(choices=ACCESSORY_STATUS_CHOICES)
    accessory_remark = serializers.CharField(required=False, allow_blank=True)
    environment_temp = serializers.FloatField(required=False)
    environment_humidity = serializers.FloatField(required=False)
    calibration_method = serializers.CharField(max_length=200, required=False)
    conclusion = serializers.CharField(max_length=500)
    closing_remark = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)


class AcceptanceRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    appointment_id = serializers.IntegerField()
    acceptor = serializers.CharField(max_length=50)
    result = serializers.BooleanField()
    opinion = serializers.CharField(max_length=500)
    acceptance_date = serializers.DateTimeField(read_only=True)


class StatusTransitionSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    target_status = serializers.ChoiceField(choices=STATUS_CHOICES)
    remark = serializers.CharField(required=False, allow_blank=True)


class WarningAppointmentSerializer(serializers.Serializer):
    warning_id = serializers.IntegerField()
    purpose = serializers.CharField(max_length=500)


class WarningFilterSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=WARNING_LEVEL_CHOICES, required=False)
    status = serializers.ChoiceField(choices=WARNING_STATUS_CHOICES, required=False)
    region_id = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)
    responsible_person_id = serializers.IntegerField(required=False)


class AnomalyTaskSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    anomaly_no = serializers.CharField(max_length=50, read_only=True)
    appointment_id = serializers.IntegerField()
    instrument_id = serializers.IntegerField()
    calibration_record_id = serializers.IntegerField(required=False, allow_null=True)
    acceptance_record_id = serializers.IntegerField(required=False, allow_null=True)
    anomaly_type = serializers.ChoiceField(choices=ANOMALY_TYPE_CHOICES)
    anomaly_level = serializers.ChoiceField(choices=ANOMALY_LEVEL_CHOICES)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=ANOMALY_STATUS_CHOICES, read_only=True)
    responsible_person_id = serializers.IntegerField(required=False, allow_null=True)
    discoverer = serializers.CharField(max_length=50, required=False, allow_blank=True)
    discovered_at = serializers.DateTimeField(required=False, allow_null=True)
    closed_at = serializers.DateTimeField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class AnomalyProcessRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    anomaly_task_id = serializers.IntegerField()
    step = serializers.ChoiceField(choices=ANOMALY_STEP_CHOICES)
    operator = serializers.CharField(max_length=50)
    operator_role = serializers.CharField(max_length=50, required=False, allow_blank=True)
    content = serializers.CharField(max_length=2000)
    result = serializers.CharField(max_length=500, required=False, allow_blank=True)
    remark = serializers.CharField(max_length=500, required=False, allow_blank=True)
    operated_at = serializers.DateTimeField(read_only=True)


class AnomalyCreateSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    anomaly_type = serializers.ChoiceField(choices=ANOMALY_TYPE_CHOICES)
    anomaly_level = serializers.ChoiceField(choices=ANOMALY_LEVEL_CHOICES)
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    calibration_record_id = serializers.IntegerField(required=False, allow_null=True)
    acceptance_record_id = serializers.IntegerField(required=False, allow_null=True)


class AnomalyAnalysisSerializer(serializers.Serializer):
    anomaly_task_id = serializers.IntegerField()
    cause_analysis = serializers.CharField(max_length=2000)
    root_cause = serializers.CharField(max_length=500, required=False, allow_blank=True)


class AnomalyRectificationSerializer(serializers.Serializer):
    anomaly_task_id = serializers.IntegerField()
    rectification_measures = serializers.CharField(max_length=2000)
    responsible_person = serializers.CharField(max_length=50, required=False, allow_blank=True)
    completion_deadline = serializers.DateField(required=False, allow_null=True)


class AnomalyReviewSerializer(serializers.Serializer):
    anomaly_task_id = serializers.IntegerField()
    review_opinion = serializers.CharField(max_length=1000)
    review_result = serializers.ChoiceField(choices=[('pass', '通过'), ('reject', '退回')])


class AnomalyCloseSerializer(serializers.Serializer):
    anomaly_task_id = serializers.IntegerField()
    conclusion = serializers.CharField(max_length=1000)
    closing_remark = serializers.CharField(max_length=500, required=False, allow_blank=True)


class AnomalyFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ANOMALY_STATUS_CHOICES, required=False)
    anomaly_level = serializers.ChoiceField(choices=ANOMALY_LEVEL_CHOICES, required=False)
    anomaly_type = serializers.ChoiceField(choices=ANOMALY_TYPE_CHOICES, required=False)
    region_id = serializers.IntegerField(required=False)
    category_id = serializers.IntegerField(required=False)
    responsible_person_id = serializers.IntegerField(required=False)
    instrument_id = serializers.IntegerField(required=False)
    appointment_id = serializers.IntegerField(required=False)


class ChangeRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    change_no = serializers.CharField(max_length=50, read_only=True)
    appointment_id = serializers.IntegerField()
    applicant = serializers.CharField(max_length=50, required=False)
    change_type = serializers.ChoiceField(choices=CHANGE_TYPE_CHOICES)
    old_value = serializers.CharField(max_length=500)
    new_value = serializers.CharField(max_length=500)
    reason = serializers.CharField(max_length=1000)
    expected_effective_date = serializers.DateField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=CHANGE_STATUS_CHOICES, read_only=True)
    related_anomaly_id = serializers.IntegerField(required=False, allow_null=True)
    related_warning_id = serializers.IntegerField(required=False, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class ChangeRequestCreateSerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    change_type = serializers.ChoiceField(choices=CHANGE_TYPE_CHOICES)
    old_value = serializers.CharField(max_length=500)
    new_value = serializers.CharField(max_length=500)
    reason = serializers.CharField(max_length=1000)
    expected_effective_date = serializers.DateField(required=False, allow_null=True)
    related_anomaly_id = serializers.IntegerField(required=False, allow_null=True)
    related_warning_id = serializers.IntegerField(required=False, allow_null=True)


class ChangeRequestAuditSerializer(serializers.Serializer):
    change_request_id = serializers.IntegerField()
    result = serializers.ChoiceField(choices=CHANGE_AUDIT_RESULT_CHOICES)
    opinion = serializers.CharField(max_length=500)


class ChangeAuditRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    change_request_id = serializers.IntegerField()
    auditor = serializers.CharField(max_length=50)
    result = serializers.ChoiceField(choices=CHANGE_AUDIT_RESULT_CHOICES)
    opinion = serializers.CharField(max_length=500)
    audit_date = serializers.DateTimeField(read_only=True)


class ChangeRequestFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=CHANGE_STATUS_CHOICES, required=False)
    change_type = serializers.ChoiceField(choices=CHANGE_TYPE_CHOICES, required=False)
    instrument_id = serializers.IntegerField(required=False)
    applicant = serializers.CharField(max_length=50, required=False)
    appointment_id = serializers.IntegerField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
