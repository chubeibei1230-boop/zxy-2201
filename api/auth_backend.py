from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from .database import users_table, UserQuery
import hashlib


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


class TinyDBBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        if not username or not password:
            return None

        user_record = users_table.get(UserQuery.username == username)
        if not user_record:
            return None

        hashed_pwd = hash_password(password)
        if user_record.get('password') != hashed_pwd:
            return None

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = User(username=username)
            user.set_unusable_password()
            user.is_active = True
            user.save()

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
