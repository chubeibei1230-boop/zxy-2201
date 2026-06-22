from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import *
from .permissions import *
from .database import *
from .services import *
from .auth_backend import hash_password
from datetime import datetime, timedelta


# ==================== Auth 相关 ====================

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        hashed_pwd = hash_password(password)

        user_record = users_table.get(UserQuery.username == username)
        if not user_record or user_record.get('password') != hashed_pwd:
            return Response({'detail': '用户名或密码错误'}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth.models import User
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = User(username=username)
            user.set_unusable_password()
            user.is_active = True
            user.save()

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user_record.get('id'),
                'username': user_record.get('username'),
                'role': user_record.get('role'),
                'name': user_record.get('name'),
                'department': user_record.get('department')
            }
        })


class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_record = users_table.get(UserQuery.username == request.user.username)
        if not user_record:
            return Response({'detail': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'id': user_record.get('id'),
            'username': user_record.get('username'),
            'role': user_record.get('role'),
            'name': user_record.get('name'),
            'department': user_record.get('department'),
            'phone': user_record.get('phone'),
            'email': user_record.get('email')
        })


# ==================== 用户管理（仅管理员） ====================

class UserListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = users_table.all()
        return Response(users)

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(users_table)
        data = {
            'id': obj_id,
            'username': serializer.validated_data['username'],
            'password': hash_password('123456'),
            'role': serializer.validated_data['role'],
            'name': serializer.validated_data.get('name', ''),
            'department': serializer.validated_data.get('department', ''),
            'phone': serializer.validated_data.get('phone', ''),
            'email': serializer.validated_data.get('email', ''),
            'created_at': now_str()
        }
        users_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        user = users_table.get(UserQuery.id == int(pk))
        if not user:
            return Response({'detail': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(user)

    def put(self, request, pk):
        user = users_table.get(UserQuery.id == int(pk))
        if not user:
            return Response({'detail': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = {**user, **serializer.validated_data}
        if 'password' in serializer.validated_data:
            data['password'] = hash_password(serializer.validated_data['password'])

        doc_id = user.doc_id
        users_table.update(data, doc_ids=[doc_id])
        return Response(data)

    def delete(self, request, pk):
        user = users_table.get(UserQuery.id == int(pk))
        if not user:
            return Response({'detail': '用户不存在'}, status=status.HTTP_404_NOT_FOUND)
        doc_id = user.doc_id
        users_table.remove(doc_ids=[doc_id])
        return Response({'message': '删除成功'})


# ==================== 基础数据管理 ====================

class InstrumentCategoryViewSet(ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]

    def list(self, request):
        data = instrument_categories_table.all()
        return Response(data)

    def retrieve(self, request, pk=None):
        data = instrument_categories_table.get(InstrumentCategoryQuery.id == int(pk))
        if not data:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def create(self, request):
        serializer = InstrumentCategorySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(instrument_categories_table)
        data = {
            'id': obj_id,
            'name': serializer.validated_data['name'],
            'code': serializer.validated_data['code'],
            'description': serializer.validated_data.get('description', ''),
            'created_at': now_str()
        }
        instrument_categories_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        record = instrument_categories_table.get(InstrumentCategoryQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InstrumentCategorySerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = {**record, **serializer.validated_data}
        doc_id = record.doc_id
        instrument_categories_table.update(data, doc_ids=[doc_id])
        return Response(data)

    def destroy(self, request, pk=None):
        record = instrument_categories_table.get(InstrumentCategoryQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        doc_id = record.doc_id
        instrument_categories_table.remove(doc_ids=[doc_id])
        return Response({'message': '删除成功'})


class ExperimentRegionViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = ExperimentRegionSerializer

    def list(self, request):
        data = experiment_regions_table.all()
        return Response(data)

    def retrieve(self, request, pk=None):
        data = experiment_regions_table.get(ExperimentRegionQuery.id == int(pk))
        if not data:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def create(self, request):
        serializer = ExperimentRegionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(experiment_regions_table)
        data = {
            'id': obj_id,
            'name': serializer.validated_data['name'],
            'code': serializer.validated_data['code'],
            'department': serializer.validated_data.get('department', ''),
            'description': serializer.validated_data.get('description', ''),
            'created_at': now_str()
        }
        experiment_regions_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        record = experiment_regions_table.get(ExperimentRegionQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExperimentRegionSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = {**record, **serializer.validated_data}
        doc_id = record.doc_id
        experiment_regions_table.update(data, doc_ids=[doc_id])
        return Response(data)

    def destroy(self, request, pk=None):
        record = experiment_regions_table.get(ExperimentRegionQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        doc_id = record.doc_id
        experiment_regions_table.remove(doc_ids=[doc_id])
        return Response({'message': '删除成功'})


class StorageLocationViewSet(ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]

    def list(self, request):
        data = storage_locations_table.all()
        return Response(data)

    def retrieve(self, request, pk=None):
        data = storage_locations_table.get(StorageLocationQuery.id == int(pk))
        if not data:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def create(self, request):
        serializer = StorageLocationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(storage_locations_table)
        data = {
            'id': obj_id,
            'name': serializer.validated_data['name'],
            'code': serializer.validated_data['code'],
            'building': serializer.validated_data.get('building', ''),
            'floor': serializer.validated_data.get('floor', ''),
            'room': serializer.validated_data.get('room', ''),
            'description': serializer.validated_data.get('description', ''),
            'created_at': now_str()
        }
        storage_locations_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        record = storage_locations_table.get(StorageLocationQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = StorageLocationSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = {**record, **serializer.validated_data}
        doc_id = record.doc_id
        storage_locations_table.update(data, doc_ids=[doc_id])
        return Response(data)

    def destroy(self, request, pk=None):
        record = storage_locations_table.get(StorageLocationQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        doc_id = record.doc_id
        storage_locations_table.remove(doc_ids=[doc_id])
        return Response({'message': '删除成功'})


class ResponsiblePersonViewSet(ModelViewSet):
    permission_classes = [IsAdminOrReadOnly]

    def list(self, request):
        data = responsible_persons_table.all()
        return Response(data)

    def retrieve(self, request, pk=None):
        data = responsible_persons_table.get(ResponsiblePersonQuery.id == int(pk))
        if not data:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def create(self, request):
        serializer = ResponsiblePersonSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(responsible_persons_table)
        data = {
            'id': obj_id,
            'name': serializer.validated_data['name'],
            'department': serializer.validated_data['department'],
            'phone': serializer.validated_data['phone'],
            'email': serializer.validated_data.get('email', ''),
            'created_at': now_str()
        }
        responsible_persons_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        record = responsible_persons_table.get(ResponsiblePersonQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ResponsiblePersonSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = {**record, **serializer.validated_data}
        doc_id = record.doc_id
        responsible_persons_table.update(data, doc_ids=[doc_id])
        return Response(data)

    def destroy(self, request, pk=None):
        record = responsible_persons_table.get(ResponsiblePersonQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        doc_id = record.doc_id
        responsible_persons_table.remove(doc_ids=[doc_id])
        return Response({'message': '删除成功'})


class CalibrationRuleViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = CalibrationRuleSerializer

    def list(self, request):
        data = calibration_rules_table.all()
        return Response(data)

    def retrieve(self, request, pk=None):
        data = calibration_rules_table.get(CalibrationRuleQuery.id == int(pk))
        if not data:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def create(self, request):
        serializer = CalibrationRuleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(calibration_rules_table)
        data = {
            'id': obj_id,
            'name': serializer.validated_data['name'],
            'instrument_category_id': serializer.validated_data['instrument_category_id'],
            'cycle_days': serializer.validated_data['cycle_days'],
            'tolerance': serializer.validated_data.get('tolerance', 0),
            'standard_value': serializer.validated_data.get('standard_value', 0),
            'unit': serializer.validated_data.get('unit', ''),
            'description': serializer.validated_data.get('description', ''),
            'created_at': now_str()
        }
        calibration_rules_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        record = calibration_rules_table.get(CalibrationRuleQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CalibrationRuleSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = {**record, **serializer.validated_data}
        doc_id = record.doc_id
        calibration_rules_table.update(data, doc_ids=[doc_id])
        return Response(data)

    def destroy(self, request, pk=None):
        record = calibration_rules_table.get(CalibrationRuleQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        doc_id = record.doc_id
        calibration_rules_table.remove(doc_ids=[doc_id])
        return Response({'message': '删除成功'})


class InstrumentViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin):
    permission_classes = [IsAdminOrReadOnly]
    serializer_class = InstrumentSerializer

    def list(self, request):
        data = instruments_table.all()
        return Response(data)

    def retrieve(self, request, pk=None):
        data = instruments_table.get(InstrumentQuery.id == int(pk))
        if not data:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def create(self, request):
        serializer = InstrumentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(instruments_table)
        data = {
            'id': obj_id,
            'serial_number': serializer.validated_data['serial_number'],
            'name': serializer.validated_data['name'],
            'category_id': serializer.validated_data['category_id'],
            'model': serializer.validated_data.get('model', ''),
            'manufacturer': serializer.validated_data.get('manufacturer', ''),
            'purchase_date': str(serializer.validated_data.get('purchase_date', '')),
            'region_id': serializer.validated_data['region_id'],
            'location_id': serializer.validated_data['location_id'],
            'responsible_person_id': serializer.validated_data['responsible_person_id'],
            'rule_id': serializer.validated_data['rule_id'],
            'status': serializer.validated_data.get('status', 'active'),
            'description': serializer.validated_data.get('description', ''),
            'created_at': now_str()
        }
        instruments_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        record = instruments_table.get(InstrumentQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = InstrumentSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = {**record, **serializer.validated_data}
        if 'purchase_date' in serializer.validated_data:
            data['purchase_date'] = str(serializer.validated_data['purchase_date'])
        doc_id = record.doc_id
        instruments_table.update(data, doc_ids=[doc_id])
        return Response(data)

    def destroy(self, request, pk=None):
        record = instruments_table.get(InstrumentQuery.id == int(pk))
        if not record:
            return Response({'detail': '不存在'}, status=status.HTTP_404_NOT_FOUND)
        doc_id = record.doc_id
        instruments_table.remove(doc_ids=[doc_id])
        return Response({'message': '删除成功'})


# ==================== 实验员功能 ====================

class AppointmentCreateView(APIView):
    permission_classes = [IsExperimenter]

    def post(self, request):
        serializer = CalibrationAppointmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        instrument_id = serializer.validated_data['instrument_id']
        expected_date = str(serializer.validated_data['expected_date'])

        if check_duplicate_calibration(instrument_id, expected_date):
            return Response({'detail': '该仪器在该日期已有待处理的校准预约'}, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(calibration_appointments_table)

        today = datetime.now().strftime('%y%m%d')
        all_appointments = calibration_appointments_table.all()
        today_appointments = [
            apt for apt in all_appointments
            if apt.get('appointment_no', '').startswith(today)
        ]
        seq = len(today_appointments) + 1
        appointment_no = f'{today}{seq:04d}'

        user_record = users_table.get(UserQuery.username == request.user.username)
        applicant_name = user_record.get('name', request.user.username)
        department = user_record.get('department', '')

        data = {
            'id': obj_id,
            'appointment_no': appointment_no,
            'instrument_id': instrument_id,
            'applicant': applicant_name,
            'department': department,
            'purpose': serializer.validated_data['purpose'],
            'expected_date': expected_date,
            'status': 'pending_submit',
            'has_precheck': serializer.validated_data.get('has_precheck', False),
            'precheck_id': serializer.validated_data.get('precheck_id'),
            'remark': serializer.validated_data.get('remark', ''),
            'created_at': now_str(),
            'submitted_at': None
        }
        calibration_appointments_table.insert(data)
        return Response(data, status=status.HTTP_201_CREATED)


class AppointmentSubmitView(APIView):
    permission_classes = [IsExperimenter]

    def post(self, request):
        serializer = AppointmentSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appointment_id = serializer.validated_data['appointment_id']
        apt = calibration_appointments_table.get(CalibrationAppointmentQuery.id == appointment_id)

        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        if apt.get('status') != 'pending_submit':
            return Response({'detail': '当前状态不允许提交审核'}, status=status.HTTP_400_BAD_REQUEST)

        if not apt.get('has_precheck') or not apt.get('precheck_id'):
            return Response({'detail': '请先完成前置检查后再提交审核'}, status=status.HTTP_400_BAD_REQUEST)

        precheck = precheck_records_table.get(PrecheckRecordQuery.id == apt.get('precheck_id'))
        if not precheck or not precheck.get('overall_result'):
            return Response({'detail': '前置检查未通过，无法提交审核'}, status=status.HTTP_400_BAD_REQUEST)

        if check_duplicate_calibration(apt.get('instrument_id'), apt.get('expected_date'), apt.get('id')):
            return Response({'detail': '该仪器在该日期已有待处理的校准预约'}, status=status.HTTP_400_BAD_REQUEST)

        data = {
            **apt,
            'status': 'pending_audit',
            'submitted_at': now_str()
        }
        doc_id = apt.doc_id
        calibration_appointments_table.update(data, doc_ids=[doc_id])

        update_warning_status_from_appointment(appointment_id)

        return Response({'message': '提交审核成功', 'data': data})


class PrecheckCreateView(APIView):
    permission_classes = [IsExperimenter]

    def post(self, request):
        serializer = PrecheckRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appointment_id = serializer.validated_data['appointment_id']
        apt = calibration_appointments_table.get(CalibrationAppointmentQuery.id == appointment_id)

        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        if apt.get('status') not in ['pending_submit', 'pending_calibration']:
            return Response({'detail': '当前状态不允许创建前置检查'}, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(precheck_records_table)
        user_record = users_table.get(UserQuery.username == request.user.username)
        experimenter_name = user_record.get('name', request.user.username)

        data = {
            'id': obj_id,
            'appointment_id': appointment_id,
            'experimenter': experimenter_name,
            'check_date': str(serializer.validated_data['check_date']),
            'items': serializer.validated_data['items'],
            'overall_result': serializer.validated_data['overall_result'],
            'remark': serializer.validated_data.get('remark', ''),
            'created_at': now_str()
        }
        precheck_records_table.insert(data)

        apt_data = {
            **apt,
            'has_precheck': True,
            'precheck_id': obj_id
        }
        doc_id = apt.doc_id
        calibration_appointments_table.update(apt_data, doc_ids=[doc_id])

        return Response(data, status=status.HTTP_201_CREATED)


# ==================== 审核人功能 ====================

class AuditView(APIView):
    permission_classes = [IsAuditor]

    def post(self, request):
        serializer = AuditRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appointment_id = serializer.validated_data['appointment_id']
        result = serializer.validated_data['result']
        opinion = serializer.validated_data['opinion']

        apt = calibration_appointments_table.get(CalibrationAppointmentQuery.id == appointment_id)
        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        if apt.get('status') != 'pending_audit':
            return Response({'detail': '当前状态不允许审核'}, status=status.HTTP_400_BAD_REQUEST)

        user_record = users_table.get(UserQuery.username == request.user.username)
        auditor_name = user_record.get('name', request.user.username)

        audit_obj_id = generate_id(audit_records_table)
        audit_data = {
            'id': audit_obj_id,
            'appointment_id': appointment_id,
            'auditor': auditor_name,
            'result': result,
            'opinion': opinion,
            'audit_date': now_str()
        }
        audit_records_table.insert(audit_data)

        if result == 'approved':
            new_status = 'pending_calibration'
        elif result == 'returned':
            new_status = 'pending_submit'
        elif result == 'rejected':
            new_status = 'rejected'
        else:
            return Response({'detail': '无效的审核结果'}, status=status.HTTP_400_BAD_REQUEST)

        apt_data = {
            **apt,
            'status': new_status
        }
        doc_id = apt.doc_id
        calibration_appointments_table.update(apt_data, doc_ids=[doc_id])

        update_warning_status_from_appointment(appointment_id)

        return Response({
            'message': '审核完成',
            'audit': audit_data,
            'appointment': apt_data
        })


# ==================== 校准员功能 ====================

class CalibrationStartView(APIView):
    permission_classes = [IsCalibrator]

    def post(self, request):
        appointment_id = request.data.get('appointment_id')
        if not appointment_id:
            return Response({'detail': '缺少appointment_id'}, status=status.HTTP_400_BAD_REQUEST)

        apt = calibration_appointments_table.get(CalibrationAppointmentQuery.id == int(appointment_id))
        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        if apt.get('status') != 'pending_calibration':
            return Response({'detail': '当前状态不允许开始校准'}, status=status.HTTP_400_BAD_REQUEST)

        if not apt.get('has_precheck') or not apt.get('precheck_id'):
            return Response({'detail': '需要先完成前置检查'}, status=status.HTTP_400_BAD_REQUEST)

        precheck = precheck_records_table.get(PrecheckRecordQuery.id == apt.get('precheck_id'))
        if not precheck or not precheck.get('overall_result'):
            return Response({'detail': '前置检查未通过，无法开始校准'}, status=status.HTTP_400_BAD_REQUEST)

        data = {
            **apt,
            'status': 'calibrating'
        }
        doc_id = apt.doc_id
        calibration_appointments_table.update(data, doc_ids=[doc_id])

        update_warning_status_from_appointment(int(appointment_id))

        return Response({'message': '开始校准', 'data': data})


class CalibrationRecordView(APIView):
    permission_classes = [IsCalibrator]

    def post(self, request):
        serializer = CalibrationRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appointment_id = serializer.validated_data['appointment_id']
        apt = calibration_appointments_table.get(CalibrationAppointmentQuery.id == appointment_id)

        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        if apt.get('status') != 'calibrating':
            return Response({'detail': '当前状态不允许记录校准结果'}, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(calibration_records_table)
        user_record = users_table.get(UserQuery.username == request.user.username)
        calibrator_name = user_record.get('name', request.user.username)

        standard_value = serializer.validated_data.get('standard_value', 0)
        measured_value = serializer.validated_data.get('measured_value', 0)
        error_value = measured_value - standard_value

        deviation_level = serializer.validated_data['deviation_level']

        start_date = serializer.validated_data.get('start_date')
        end_date = serializer.validated_data.get('end_date')

        data = {
            'id': obj_id,
            'appointment_id': appointment_id,
            'calibrator': calibrator_name,
            'start_date': str(start_date) if start_date else None,
            'end_date': str(end_date) if end_date else None,
            'standard_value': standard_value,
            'measured_value': measured_value,
            'error_value': error_value,
            'deviation_level': deviation_level,
            'accessory_status': serializer.validated_data['accessory_status'],
            'accessory_remark': serializer.validated_data.get('accessory_remark', ''),
            'environment_temp': serializer.validated_data.get('environment_temp'),
            'environment_humidity': serializer.validated_data.get('environment_humidity'),
            'calibration_method': serializer.validated_data.get('calibration_method', ''),
            'conclusion': serializer.validated_data['conclusion'],
            'closing_remark': serializer.validated_data.get('closing_remark', ''),
            'created_at': now_str()
        }
        calibration_records_table.insert(data)

        if deviation_level in ['minor', 'major', 'critical']:
            new_status = 'deviation_pending'
        else:
            new_status = 'pending_acceptance'

        apt_data = {
            **apt,
            'status': new_status
        }
        doc_id = apt.doc_id
        calibration_appointments_table.update(apt_data, doc_ids=[doc_id])

        update_warning_status_from_appointment(appointment_id)

        return Response({
            'message': '校准记录已保存',
            'calibration': data,
            'appointment': apt_data
        })


class AcceptanceView(APIView):
    permission_classes = [IsAdminOrExperimenter]

    def post(self, request):
        serializer = AcceptanceRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        appointment_id = serializer.validated_data['appointment_id']
        apt = calibration_appointments_table.get(CalibrationAppointmentQuery.id == appointment_id)

        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        if apt.get('status') not in ['pending_acceptance', 'deviation_pending']:
            return Response({'detail': '当前状态不允许验收'}, status=status.HTTP_400_BAD_REQUEST)

        obj_id = generate_id(acceptance_records_table)
        user_record = users_table.get(UserQuery.username == request.user.username)
        acceptor_name = user_record.get('name', request.user.username)

        data = {
            'id': obj_id,
            'appointment_id': appointment_id,
            'acceptor': acceptor_name,
            'result': serializer.validated_data['result'],
            'opinion': serializer.validated_data['opinion'],
            'acceptance_date': now_str()
        }
        acceptance_records_table.insert(data)

        apt_data = {
            **apt,
            'status': 'closed'
        }
        doc_id = apt.doc_id
        calibration_appointments_table.update(apt_data, doc_ids=[doc_id])

        update_warning_status_from_appointment(appointment_id)

        return Response({
            'message': '验收完成',
            'acceptance': data,
            'appointment': apt_data
        })


# ==================== 查询和统计 ====================

class AppointmentFilterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        department = request.query_params.get('department')
        category_id = request.query_params.get('category_id')
        applicant = request.query_params.get('applicant')
        status = request.query_params.get('status')
        audit_status = request.query_params.get('audit_status')
        instrument_status = request.query_params.get('instrument_status')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        appointments = calibration_appointments_table.all()

        if department:
            appointments = [a for a in appointments if department in a.get('department', '')]
        if category_id:
            category_id = int(category_id)
            filtered = []
            for a in appointments:
                inst = instruments_table.get(InstrumentQuery.id == a.get('instrument_id'))
                if inst and inst.get('category_id') == category_id:
                    filtered.append(a)
            appointments = filtered
        if applicant:
            appointments = [a for a in appointments if applicant in a.get('applicant', '')]
        if status:
            appointments = [a for a in appointments if a.get('status') == status]
        if audit_status:
            filtered = []
            for a in appointments:
                audit_records = audit_records_table.search(
                    AuditRecordQuery.appointment_id == a.get('id')
                )
                if audit_records:
                    latest_audit = sorted(audit_records, key=lambda x: x.get('audit_date', ''), reverse=True)[0]
                    if latest_audit.get('result') == audit_status:
                        filtered.append(a)
                elif audit_status == 'pending':
                    if a.get('status') in ['pending_audit', 'pending_submit']:
                        filtered.append(a)
            appointments = filtered
        if instrument_status:
            filtered = []
            for a in appointments:
                inst = instruments_table.get(InstrumentQuery.id == a.get('instrument_id'))
                if inst and inst.get('status') == instrument_status:
                    filtered.append(a)
            appointments = filtered
        if start_date:
            appointments = [a for a in appointments if a.get('expected_date', '') >= start_date]
        if end_date:
            appointments = [a for a in appointments if a.get('expected_date', '') <= end_date]

        result = []
        for apt in appointments:
            full_info = get_appointment_full_info(apt.get('id'))
            if full_info:
                result.append(full_info)

        return Response(result)


class PendingAuditListView(APIView):
    permission_classes = [IsAdminOrAuditor]

    def get(self, request):
        appointments = calibration_appointments_table.search(
            CalibrationAppointmentQuery.status == 'pending_audit'
        )
        result = []
        for apt in appointments:
            full_info = get_appointment_full_info(apt.get('id'))
            if full_info:
                result.append(full_info)
        return Response(result)


class DeviationDistributionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        records = calibration_records_table.all()

        distribution = {
            'none': 0,
            'minor': 0,
            'major': 0,
            'critical': 0
        }

        region_distribution = {}
        category_distribution = {}

        for record in records:
            level = record.get('deviation_level', 'none')
            if level in distribution:
                distribution[level] += 1

            apt = calibration_appointments_table.get(CalibrationAppointmentQuery.id == record.get('appointment_id'))
            if not apt:
                continue
            inst = instruments_table.get(InstrumentQuery.id == apt.get('instrument_id'))
            if not inst:
                continue

            region_id = inst.get('region_id')
            region = experiment_regions_table.get(ExperimentRegionQuery.id == region_id)
            region_name = region.get('name', f'区域{region_id}') if region else f'区域{region_id}'
            if region_name not in region_distribution:
                region_distribution[region_name] = {'none': 0, 'minor': 0, 'major': 0, 'critical': 0}
            region_distribution[region_name][level] += 1

            category_id = inst.get('category_id')
            category = instrument_categories_table.get(InstrumentCategoryQuery.id == category_id)
            category_name = category.get('name', f'类别{category_id}') if category else f'类别{category_id}'
            if category_name not in category_distribution:
                category_distribution[category_name] = {'none': 0, 'minor': 0, 'major': 0, 'critical': 0}
            category_distribution[category_name][level] += 1

        return Response({
            'overall': distribution,
            'by_region': region_distribution,
            'by_category': category_distribution
        })


class CalibrationEfficiencyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        all_appointments = calibration_appointments_table.search(
            CalibrationAppointmentQuery.created_at >= start_date
        )

        total = len(all_appointments)
        closed = len([a for a in all_appointments if a.get('status') == 'closed'])
        rejected = len([a for a in all_appointments if a.get('status') == 'rejected'])
        pending = total - closed - rejected

        avg_duration = 0
        durations = []
        calibrator_stats = {}

        for apt in all_appointments:
            if apt.get('status') == 'closed':
                cal_records = calibration_records_table.search(
                    CalibrationRecordQuery.appointment_id == apt.get('id')
                )
                for cal in cal_records:
                    calibrator = cal.get('calibrator', '未知')
                    if calibrator not in calibrator_stats:
                        calibrator_stats[calibrator] = {'count': 0, 'total_duration': 0}
                    calibrator_stats[calibrator]['count'] += 1

                    if cal.get('start_date') and cal.get('end_date'):
                        try:
                            start = datetime.strptime(cal['start_date'], '%Y-%m-%d %H:%M:%S')
                            end = datetime.strptime(cal['end_date'], '%Y-%m-%d %H:%M:%S')
                            duration_hours = (end - start).total_seconds() / 3600
                            durations.append(duration_hours)
                            calibrator_stats[calibrator]['total_duration'] += duration_hours
                        except:
                            pass

        if durations:
            avg_duration = sum(durations) / len(durations)

        for cal in calibrator_stats:
            if calibrator_stats[cal]['count'] > 0:
                calibrator_stats[cal]['avg_duration'] = calibrator_stats[cal]['total_duration'] / calibrator_stats[cal]['count']
            else:
                calibrator_stats[cal]['avg_duration'] = 0

        completion_rate = (closed / total * 100) if total > 0 else 0

        return Response({
            'period_days': days,
            'total': total,
            'closed': closed,
            'rejected': rejected,
            'pending': pending,
            'completion_rate': round(completion_rate, 2),
            'avg_duration_hours': round(avg_duration, 2),
            'by_calibrator': calibrator_stats
        })


class SystemCheckView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        result = run_all_checks()
        return Response(result)


class AppointmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        appointments = apt_table.all()
        result = []
        for apt in appointments:
            info = get_appointment_full_info(apt.get('id'))
            if info:
                result.append(info)
        return Response(result)


class AppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        info = get_appointment_full_info(pk)
        if not info:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(info)

    def put(self, request, pk):
        apt = apt_table.get(CalibrationAppointmentQuery.id == int(pk))
        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CalibrationAppointmentSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if apt.get('status') != 'pending_submit':
            return Response({'detail': '仅草稿状态可修改'}, status=status.HTTP_400_BAD_REQUEST)

        instrument_id = serializer.validated_data.get('instrument_id', apt.get('instrument_id'))
        expected_date = serializer.validated_data.get('expected_date', apt.get('expected_date'))
        if check_duplicate_calibration(instrument_id, str(expected_date), int(pk)):
            return Response({'detail': '该仪器在该日期已有校准安排'}, status=status.HTTP_400_BAD_REQUEST)

        update_data = {}
        for key in ['instrument_id', 'purpose', 'expected_date', 'department', 'remark']:
            if key in serializer.validated_data:
                update_data[key] = str(serializer.validated_data[key]) if key == 'expected_date' else serializer.validated_data[key]

        doc_id = apt.doc_id
        apt_table.update(update_data, doc_ids=[doc_id])
        updated = get_appointment_full_info(int(pk))
        return Response(updated)

    def delete(self, request, pk):
        apt = apt_table.get(CalibrationAppointmentQuery.id == int(pk))
        if not apt:
            return Response({'detail': '预约不存在'}, status=status.HTTP_404_NOT_FOUND)

        if apt.get('status') != 'pending_submit':
            return Response({'detail': '仅草稿状态可删除'}, status=status.HTTP_400_BAD_REQUEST)

        doc_id = apt.doc_id
        apt_table.remove(doc_ids=[doc_id])

        update_warning_status_from_appointment(int(pk))

        return Response({'message': '删除成功'})


# ==================== 预警与续检闭环 ====================

class WarningListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        level = request.query_params.get('level')
        warning_status = request.query_params.get('status')
        region_id = request.query_params.get('region_id')
        category_id = request.query_params.get('category_id')
        responsible_person_id = request.query_params.get('responsible_person_id')

        result = list_warnings(
            level=level,
            status=warning_status,
            region_id=region_id,
            category_id=category_id,
            responsible_person_id=responsible_person_id
        )
        return Response(result)


class WarningDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        info = get_warning_full_info(pk)
        if not info:
            return Response({'detail': '预警记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(info)


class WarningCreateAppointmentView(APIView):
    permission_classes = [IsExperimenter]

    def post(self, request):
        serializer = WarningAppointmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        warning_id = serializer.validated_data['warning_id']
        purpose = serializer.validated_data['purpose']

        appointment_data, error = create_warning_appointment(
            warning_id=warning_id,
            username=request.user.username,
            purpose=purpose
        )

        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': '续检申请创建成功',
            'appointment': appointment_data
        }, status=status.HTTP_201_CREATED)


class WarningDetectView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        generated = run_warning_detection()
        return Response({
            'message': '预警检测完成',
            'generated_count': len(generated),
            'warnings': generated
        })


class WarningDashboardView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        dashboard = get_warning_dashboard()
        return Response(dashboard)
