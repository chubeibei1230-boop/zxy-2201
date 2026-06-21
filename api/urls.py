from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LoginView, UserInfoView,
    UserListView, UserDetailView,
    InstrumentCategoryViewSet, ExperimentRegionViewSet,
    StorageLocationViewSet, ResponsiblePersonViewSet,
    CalibrationRuleViewSet, InstrumentViewSet,
    AppointmentCreateView, AppointmentSubmitView,
    PrecheckCreateView, AuditView,
    CalibrationStartView, CalibrationRecordView,
    AcceptanceView, AppointmentFilterView,
    PendingAuditListView, DeviationDistributionView,
    CalibrationEfficiencyView, SystemCheckView,
    AppointmentListView, AppointmentDetailView
)

router = DefaultRouter()
router.register(r'instrument-categories', InstrumentCategoryViewSet, basename='instrumentcategory')
router.register(r'experiment-regions', ExperimentRegionViewSet, basename='experimentregion')
router.register(r'storage-locations', StorageLocationViewSet, basename='storagelocation')
router.register(r'responsible-persons', ResponsiblePersonViewSet, basename='responsibleperson')
router.register(r'calibration-rules', CalibrationRuleViewSet, basename='calibrationrule')
router.register(r'instruments', InstrumentViewSet, basename='instrument')

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/userinfo/', UserInfoView.as_view(), name='userinfo'),

    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),

    path('', include(router.urls)),

    path('appointments/', AppointmentListView.as_view(), name='appointment-list'),
    path('appointments/<int:pk>/', AppointmentDetailView.as_view(), name='appointment-detail'),
    path('appointments/create/', AppointmentCreateView.as_view(), name='appointment-create'),
    path('appointments/submit/', AppointmentSubmitView.as_view(), name='appointment-submit'),
    path('appointments/filter/', AppointmentFilterView.as_view(), name='appointment-filter'),

    path('prechecks/', PrecheckCreateView.as_view(), name='precheck-create'),

    path('audits/', AuditView.as_view(), name='audit'),

    path('calibrations/start/', CalibrationStartView.as_view(), name='calibration-start'),
    path('calibrations/record/', CalibrationRecordView.as_view(), name='calibration-record'),

    path('acceptances/', AcceptanceView.as_view(), name='acceptance'),

    path('reports/pending-audit/', PendingAuditListView.as_view(), name='report-pending-audit'),
    path('reports/deviation-distribution/', DeviationDistributionView.as_view(), name='report-deviation'),
    path('reports/calibration-efficiency/', CalibrationEfficiencyView.as_view(), name='report-efficiency'),

    path('system/check/', SystemCheckView.as_view(), name='system-check'),
]
