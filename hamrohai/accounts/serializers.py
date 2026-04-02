from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()



# User serializer with only required fields
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'age'
        ]


# UserProfile serializer for extra fields
from .models import UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'provider', 'created_at', 'onboarding_completed', 'onboarding_data',
            'onboarding_progress', 'chat_history', 'iq_score', 'psychological_profile',
            'roadmap', 'weekly_plan', 'chatbot_history', 'daily_plan'
        ]
