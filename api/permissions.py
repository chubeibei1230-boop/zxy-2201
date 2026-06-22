from rest_framework.permissions import BasePermission, IsAuthenticated
from .database import users_table, UserQuery


def get_user_role(username):
    user = users_table.get(UserQuery.username == username)
    return user.get('role') if user else None


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request.user.username) == 'admin'


class IsExperimenter(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request.user.username) == 'experimenter'


class IsAuditor(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request.user.username) == 'auditor'


class IsCalibrator(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request.user.username) == 'calibrator'


class IsAdminOrExperimenter(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_user_role(request.user.username)
        return role in ['admin', 'experimenter']


class IsAdminOrAuditor(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_user_role(request.user.username)
        return role in ['admin', 'auditor']


class IsAdminOrCalibrator(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_user_role(request.user.username)
        return role in ['admin', 'calibrator']


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return request.user and request.user.is_authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_role(request.user.username) == 'admin'


class IsAdminOrCalibratorOrExperimenter(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_user_role(request.user.username)
        return role in ['admin', 'calibrator', 'experimenter']


class IsAdminOrAuditorForAnomaly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_user_role(request.user.username)
        return role in ['admin', 'auditor']


class IsAdminOrExperimenterForAnomaly(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_user_role(request.user.username)
        return role in ['admin', 'experimenter']
