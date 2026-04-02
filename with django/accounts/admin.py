from django.contrib import admin
from .models import User, OTPCode

admin.site.register(User)
admin.site.register(OTPCode)
