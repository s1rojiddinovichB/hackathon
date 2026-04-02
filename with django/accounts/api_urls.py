from django.urls import path
from . import api_views

urlpatterns = [
    # Auth
    path('auth/google/', api_views.api_google_auth, name='api-google-auth'),
    path('auth/me/', api_views.api_me, name='api-me'),

    # User
    path('user/update/', api_views.api_update_user, name='api-update-user'),

    # AI / Chat
    path('chat/ask/', api_views.api_chat_ask, name='api-chat-ask'),
    path('chat/extract/', api_views.api_chat_extract, name='api-chat-extract'),
    path('chat/evaluate/', api_views.api_chat_evaluate, name='api-chat-evaluate'),

    # Profile
    path('profile/generate/', api_views.api_profile_generate, name='api-profile-generate'),
    path('roadmap/generate/', api_views.api_roadmap_generate, name='api-roadmap-generate'),
    path('weekly/generate/', api_views.api_weekly_generate, name='api-weekly-generate'),
    path('daily/generate/', api_views.api_daily_generate, name='api-daily-generate'),

    # Study Tracks
    path('tracks/', api_views.api_tracks_list, name='api-tracks-list'),
    path('tracks/create/', api_views.api_track_create, name='api-track-create'),
    path('tracks/<int:track_id>/delete/', api_views.api_track_delete, name='api-track-delete'),
    path('tracks/<int:track_id>/daily/', api_views.api_track_daily, name='api-track-daily'),
    path('tracks/<int:track_id>/weekly/', api_views.api_track_weekly, name='api-track-weekly'),
    path('tracks/<int:track_id>/roadmap/', api_views.api_track_roadmap, name='api-track-roadmap'),

    # Chatbot
    path('chatbot/message/', api_views.api_chatbot_message, name='api-chatbot-message'),
    path('chatbot/reset/', api_views.api_chatbot_reset, name='api-chatbot-reset'),

    # IQ
    path('iq/save/', api_views.api_save_iq, name='api-save-iq'),
]
