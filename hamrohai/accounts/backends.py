from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        login_email = email or username
        if not login_email or not password:
            return None
        try:
            user = User.objects.get(email=login_email)
        except User.DoesNotExist:
            return None
        if user.check_password(password):
            return user
        return None
