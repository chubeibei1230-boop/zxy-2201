from rest_framework import serializers
from .models import (
    ROLE_CHOICES, STATUS_CHOICES, AUDIT_RESULT_CHOICES,
    DEVIATION_LEVEL_CHOICES, ACCESSORY_STATUS_CHOICES
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
