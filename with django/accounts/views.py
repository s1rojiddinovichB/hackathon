import json

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from .forms import RegisterForm, LoginForm

User = get_user_model()


# ─── Landing ────────────────────────────────────────────────────────────────

def landing_view(request):
    if request.user.is_authenticated:
        if not hasattr(request.user, 'profile') or not request.user.profile.onboarding_completed:
            return redirect('onboarding')
        return redirect('dashboard')
    return render(request, 'landing.html')


# ─── Register ───────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                age=form.cleaned_data['age']
            )
            from .models import UserProfile
            UserProfile.objects.create(user=user)
            login(request, user, backend='accounts.backends.EmailBackend')
            return redirect('onboarding')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {
        'form': form,
        'google_client_id': settings.GOOGLE_CLIENT_ID
    })


# ─── Login ───────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        if not hasattr(request.user, 'profile') or not request.user.profile.onboarding_completed:
            return redirect('onboarding')
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            if user is not None:
                login(request, user, backend='accounts.backends.EmailBackend')
                if not hasattr(user, 'profile') or not user.profile.onboarding_completed:
                    return redirect('onboarding')
                return redirect('dashboard')
            else:
                messages.error(request, "Email yoki parol noto'g'ri.")
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {
        'form': form,
        'google_client_id': settings.GOOGLE_CLIENT_ID
    })


# ─── Logout ──────────────────────────────────────────────────────────────────

def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Onboarding ──────────────────────────────────────────────────────────────

@login_required
def onboarding_view(request):
    if hasattr(request.user, 'profile') and request.user.profile.onboarding_completed:
        return redirect('dashboard')

    # Load onboarding structure from file.json
    import os
    base_dir = settings.BASE_DIR
    file_json_path = os.path.join(base_dir, 'file.json')
    try:
        with open(file_json_path, 'r', encoding='utf-8') as f:
            onboarding_data = json.load(f)
    except FileNotFoundError:
        onboarding_data = {"onboarding_stages": []}

    # Only stages 1-3 (not IQ test stage 4)
    stages = [s for s in onboarding_data.get('onboarding_stages', []) if s['stage'] <= 3]

    # Restore saved progress and chat history from profile
    profile = getattr(request.user, 'profile', None)
    saved_data = profile.onboarding_data if profile else {}
    saved_history = profile.chat_history if profile else []
    saved_progress = {}
    if profile and profile.onboarding_progress:
        try:
            saved_progress = json.loads(profile.onboarding_progress)
        except Exception:
            saved_progress = {}

    context = {
        'stages_json': json.dumps(stages),
        'saved_data': json.dumps(saved_data),
        'saved_history': json.dumps(saved_history),
        'saved_progress': json.dumps(saved_progress),
    }
    return render(request, 'onboarding.html', context)


# ─── IQ Test ─────────────────────────────────────────────────────────────────

@login_required
def iq_test_view(request):
    # Load IQ stage from file.json
    import os
    base_dir = settings.BASE_DIR
    file_json_path = os.path.join(base_dir, 'file.json')
    try:
        with open(file_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"onboarding_stages": []}

    iq_stage = next((s for s in data.get('onboarding_stages', []) if s['stage'] == 4), None)

    context = {
        'iq_stage_json': json.dumps(iq_stage) if iq_stage else 'null',
    }
    return render(request, 'iq_test.html', context)


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.onboarding_completed:
        return redirect('onboarding')
    from .models import StudyTrack
    tracks = list(StudyTrack.objects.filter(user=request.user).values(
        'id', 'title', 'icon', 'description', 'daily_plan', 'weekly_plan', 'roadmap', 'created_at'
    ))
    # Convert datetimes to strings for JSON
    for t in tracks:
        t['created_at'] = t['created_at'].isoformat() if t['created_at'] else ''
    profile = getattr(request.user, 'profile', None)
    return render(request, 'accounts/dashboard.html', {
        'user': request.user,
        'chat_history_json': json.dumps(profile.chat_history if profile else []),
        'weekly_plan_json': json.dumps(profile.weekly_plan if profile else {}),
        'daily_plan_json': json.dumps(profile.daily_plan if profile else {}),
        'tracks_json': json.dumps(tracks),
    })


# ─── Profile ─────────────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.onboarding_completed:
        return redirect('onboarding')
    import datetime
    # Build last 52 weeks activity grid (all zeros for MVP — no real tracking yet)
    today = datetime.date.today()
    start = today - datetime.timedelta(weeks=52)
    # Generate date range
    activity = {}
    d = start
    while d <= today:
        activity[d.isoformat()] = 0
        d += datetime.timedelta(days=1)
    return render(request, 'accounts/profile.html', {
        'user': request.user,
        'activity_json': json.dumps(activity),
    })
