import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


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

class User(AbstractUser):
    username = None
    email = models.EmailField('Email', unique=True)
    first_name = models.CharField(max_length=150, blank=True, default='')
    last_name = models.CharField(max_length=150, blank=True, default='')
    age = models.PositiveIntegerField(default=0)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email

    def _get_profile(self):
        if not self.pk:
            return None
        try:
            profile = self.profile
        except ObjectDoesNotExist:
            profile = None
        if profile is None:
            profile, _ = UserProfile.objects.get_or_create(user=self)
            self.profile = profile
        return profile

    @staticmethod
    def _normalize_age(value):
        if value in (None, ''):
            return None
        try:
            parsed = int(value)
            return max(parsed, 0)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _age_from_birth_date(value):
        if not value:
            return None
        try:
            if isinstance(value, datetime.date):
                birth_date = value
            else:
                birth_date = datetime.date.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

        today = datetime.date.today()
        return max(
            today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day)),
            0,
        )

    def _save_profile_field(self, field_name, value):
        profile = self._get_profile()
        if profile is None:
            return
        setattr(profile, field_name, value)
        profile.save(update_fields=[field_name])

    @property
    def provider(self):
        profile = self._get_profile()
        return profile.provider if profile else 'email'

    @provider.setter
    def provider(self, value):
        self._save_profile_field('provider', value or 'email')

    @property
    def created_at(self):
        profile = self._get_profile()
        return profile.created_at if profile else self.date_joined

    @property
    def onboarding_completed(self):
        profile = self._get_profile()
        return profile.onboarding_completed if profile else False

    @onboarding_completed.setter
    def onboarding_completed(self, value):
        self._save_profile_field('onboarding_completed', bool(value))

    @property
    def onboarding_data(self):
        profile = self._get_profile()
        data = dict(profile.onboarding_data or {}) if profile else {}
        if self.first_name:
            data.setdefault('name', self.first_name)
        if self.last_name:
            data.setdefault('surname', self.last_name)
        if self.age:
            data.setdefault('age', self.age)
        return data

    @onboarding_data.setter
    def onboarding_data(self, value):
        payload = dict(value or {})
        name = payload.pop('name', None)
        surname = payload.pop('surname', None)
        explicit_age = payload.pop('age', None)

        update_fields = []
        if name is not None:
            self.first_name = str(name).strip()
            update_fields.append('first_name')
        if surname is not None:
            self.last_name = str(surname).strip()
            update_fields.append('last_name')

        age_value = self._normalize_age(explicit_age)
        if age_value is None:
            age_value = self._age_from_birth_date(payload.get('birth_date'))
        if age_value is not None:
            self.age = age_value
            update_fields.append('age')

        if self.pk and update_fields:
            self.save(update_fields=sorted(set(update_fields)))
        self._save_profile_field('onboarding_data', payload)

    @property
    def onboarding_progress(self):
        profile = self._get_profile()
        return profile.onboarding_progress if profile else None

    @onboarding_progress.setter
    def onboarding_progress(self, value):
        self._save_profile_field('onboarding_progress', value)

    @property
    def chat_history(self):
        profile = self._get_profile()
        return profile.chat_history if profile else None

    @chat_history.setter
    def chat_history(self, value):
        self._save_profile_field('chat_history', value)

    @property
    def iq_score(self):
        profile = self._get_profile()
        return profile.iq_score if profile else 0

    @iq_score.setter
    def iq_score(self, value):
        self._save_profile_field('iq_score', value or 0)

    @property
    def psychological_profile(self):
        profile = self._get_profile()
        return profile.psychological_profile if profile else None

    @psychological_profile.setter
    def psychological_profile(self, value):
        self._save_profile_field('psychological_profile', value)

    @property
    def roadmap(self):
        profile = self._get_profile()
        return profile.roadmap if profile else None

    @roadmap.setter
    def roadmap(self, value):
        self._save_profile_field('roadmap', value)

    @property
    def weekly_plan(self):
        profile = self._get_profile()
        return profile.weekly_plan if profile else None

    @weekly_plan.setter
    def weekly_plan(self, value):
        self._save_profile_field('weekly_plan', value)

    @property
    def chatbot_history(self):
        profile = self._get_profile()
        return profile.chatbot_history if profile else None

    @chatbot_history.setter
    def chatbot_history(self, value):
        self._save_profile_field('chatbot_history', value)

    @property
    def daily_plan(self):
        profile = self._get_profile()
        return profile.daily_plan if profile else None

    @daily_plan.setter
    def daily_plan(self, value):
        self._save_profile_field('daily_plan', value)


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


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
