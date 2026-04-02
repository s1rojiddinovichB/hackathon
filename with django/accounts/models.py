from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email talab qilinadi")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)



# Only keep required fields in User
class User(AbstractUser):
    username = None
    email = models.EmailField('Email', unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    age = models.PositiveIntegerField()

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email


# Move extra fields to UserProfile
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    provider = models.CharField(max_length=20, default='email')
    created_at = models.DateTimeField(auto_now_add=True)
    onboarding_completed = models.BooleanField(default=False)
    onboarding_data = models.JSONField(null=True, blank=True)
    onboarding_progress = models.TextField(null=True, blank=True)
    chat_history = models.JSONField(null=True, blank=True)
    iq_score = models.IntegerField(default=0)
    psychological_profile = models.JSONField(null=True, blank=True)
    roadmap = models.JSONField(null=True, blank=True)
    weekly_plan = models.JSONField(null=True, blank=True)
    chatbot_history = models.JSONField(null=True, blank=True)
    daily_plan = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f"Profile of {self.user.email}"


class StudyTrack(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_tracks')
    title = models.CharField(max_length=200)
    icon = models.CharField(max_length=10, default='📚')
    description = models.TextField(blank=True)
    daily_plan = models.JSONField(null=True, blank=True)
    weekly_plan = models.JSONField(null=True, blank=True)
    roadmap = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        db_table = 'study_tracks'

    def __str__(self):
        return f"{self.user.email} — {self.title}"


class OTPCode(models.Model):
    email = models.EmailField(primary_key=True)
    code = models.CharField(max_length=10)
    password_hash = models.TextField()
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.email} - {self.code}"
