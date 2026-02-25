from django.contrib.auth.backends import ModelBackend
from apps.accounts.models import User
from apps.accounts.auth_utils import normalize_mobile


class MobileBackend(ModelBackend):
    def authenticate(self, request, mobile=None, password=None, **kwargs):
        if mobile is None:
            mobile = kwargs.get("username")
        mobile = normalize_mobile(mobile)
        if not mobile or not password:
            return None
        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None