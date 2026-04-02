from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('onboarding/', views.onboarding_view, name='onboarding'),
    path('iq-test/', views.iq_test_view, name='iq_test'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
]
