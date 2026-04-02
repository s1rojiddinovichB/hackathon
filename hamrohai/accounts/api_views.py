import json

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.hashers import make_password
from django.conf import settings

from .utils import call_ollama, send_otp_email
from .serializers import UserSerializer
from .models import StudyTrack

User = get_user_model()


# ─── Auth via Google (session-based) ─────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def api_google_auth(request):
    credential = request.data.get('credential')
    if not credential:
        return Response({'detail': 'credential talab qilinadi'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as g_requests
        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        idinfo = id_token.verify_oauth2_token(credential, g_requests.Request(), client_id)
        email = idinfo['email']
        given_name = (idinfo.get('given_name') or '').strip()
        family_name = (idinfo.get('family_name') or '').strip()

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': given_name,
                'last_name': family_name,
                'age': 0,
                'password': make_password(None),
            }
        )
        if given_name and not user.first_name:
            user.first_name = given_name
        if family_name and not user.last_name:
            user.last_name = family_name
        if created or given_name or family_name:
            user.save()
        user.provider = 'google'

        login(request, user, backend='accounts.backends.EmailBackend')
        return Response({
            'status': 'success',
            'onboardingCompleted': user.onboarding_completed,
            'redirect': '/onboarding/' if not user.onboarding_completed else '/dashboard/'
        })
    except Exception as e:
        return Response({'detail': f'Google xatosi: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# ─── Current user ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    return Response({
        'status': 'success',
        'user': UserSerializer(request.user).data,
        'profile': {
            'provider': request.user.provider,
            'onboarding_completed': request.user.onboarding_completed,
            'onboarding_data': request.user.onboarding_data or {},
            'iq_score': request.user.iq_score,
            'psychological_profile': request.user.psychological_profile or {},
        }
    })


# ─── Update user data ─────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_update_user(request):
    user = request.user
    data = request.data

    if 'onboardingData' in data:
        user.onboarding_data = data['onboardingData']
    if 'onboardingCompleted' in data:
        user.onboarding_completed = data['onboardingCompleted']
    if 'onboardingProgress' in data:
        user.onboarding_progress = data['onboardingProgress']
    if 'chatHistory' in data:
        user.chat_history = data['chatHistory']
    if 'iqScore' in data:
        user.iq_score = data['iqScore']
    if 'psychologicalProfile' in data:
        user.psychological_profile = data['psychologicalProfile']
    if 'roadmap' in data:
        user.roadmap = data['roadmap']
    if 'weeklyPlan' in data:
        user.weekly_plan = data['weeklyPlan']

    user.save()
    return Response({'status': 'success', 'message': 'Saqlandi'})


# ─── AI: Ask question ─────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_chat_ask(request):
    question = request.data.get('question', '')
    options = request.data.get('options', [])
    history = request.data.get('chatHistory', [])

    prompt = f"[TIZIM TOPSHIRIG'I: Suhbatdoshdan quyidagi narsani so'rashing kerak: '{question}'."
    if options:
        if isinstance(options[0], dict):
            opt_texts = [o.get("text", f"Rasm: {o.get('id')}") for o in options if o.get("text")]
        else:
            opt_texts = options
        if opt_texts:
            prompt += f" Javob berishini osonlashtirish uchun ushbu variantlarni aytib o't: {', '.join(str(o) for o in opt_texts)}."
    prompt += " O'z rolingda, juda QISQA va xushmuomalalik bilan faqat savolni o'zini ber.]"

    content = call_ollama(prompt, history)
    if not content:
        content = question
    return Response({'response': content})


# ─── AI: Extract fields ───────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def api_chat_extract(request):
    answer = request.data.get('userAnswer', '')
    fields = request.data.get('availableFields', [])

    fields_str = ""
    for f in fields:
        fields_str += f"- {f.get('field')} (savol: {f.get('question')}, turi: {f.get('type')})\n"

    prompt = (
        f'Foydalanuvchi matni: "{answer}"\n'
        f'Vazifang: Ushbu matndan quyidagi maydonlarga mos keladigan ma\'lumotlarni ajratib ol (agar bor bo\'lsa):\n'
        f'{fields_str}\n'
        f'Qoidalar:\n'
        f'1) Faqat matnda aniq ko\'rsatilgan ma\'lumotlarni ol.\n'
        f'2) Agar ma\'lumot bo\'lmasa, uni qoldirib ket.\n'
        f'3) Javobni FAQAT JSON formatida qaytar.\n'
        f'4) JSON formati: {{"field_name": "value", ...}}.\n'
        f'5) Agar maydon "date" bo\'lsa, uni "YYYY-MM-DD" formatiga o\'tkazishga harakat qil.\n'
        f'6) Agar "select" bo\'lsa, variantlarga eng mosini tanla.\n'
        f'JSON:'
    )

    content = call_ollama(prompt)
    try:
        if content and "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif content and "```" in content:
            content = content.split("```")[1].split("```")[0]
        data = json.loads(content.strip()) if content else {}
    except Exception:
        data = {}

    return Response(data)


# ─── AI: Evaluate answer ──────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def api_chat_evaluate(request):
    question = request.data.get('question', '')
    ans = request.data.get('userAnswer', '')
    f_type = request.data.get('fieldType', 'text')
    options = request.data.get('options', [])

    eval_prompt = (
        f"Savol: '{question}'\n"
        f"Foydalanuvchining xom javobi: '{ans}'\n"
        f"1) Agar foydalanuvchi savolga yetarlicha mos javob bergan bo'lsa, 'VALID: <javob>' deb qaytar.\n"
        f"2) Aks holda 'INVALID' deb javob ber."
    )

    content = call_ollama(eval_prompt)
    if not content:
        content = f"VALID: {ans}"
    return Response({'response': content})


# ─── AI: Generate psychological profile ──────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_profile_generate(request):
    user = request.user
    onboarding_data = request.data.get('onboardingData') or user.onboarding_data or {}
    iq_score = request.data.get('iqScore') or user.iq_score or 0

    prompt = (
        f"Foydalanuvchi ma'lumoti: {json.dumps(onboarding_data, ensure_ascii=False)}\n"
        f"IQ natija: {iq_score}/47\n\n"
        f"Iltimos, quyidagi maydonlarni o'z ichiga olgan batafsil psixologik profilni JSON formatda qaytaring:\n"
        f"- summary (2-3 jumlali umumiy tavsif, o'zbek tilida)\n"
        f"- personality_type (shaxsiyat turi)\n"
        f"- mindset_label (fixed yoki growth mindset)\n"
        f"- strengths (list: 3-5 ta kuchli tomon, qisqa so'z/ibora)\n"
        f"- risk_factors (list: 2-4 ta xavf omili, qisqa so'z/ibora)\n"
        f"- recommended_subjects (list: 3-5 ta tavsiya etilgan fan/soha)\n"
        f"- weekly_study_plan (haftalik o'qish tavsiyasi, 2-3 jumla)\n"
        f"- ai_tone (do'stona, qattiq yoki neytral)\n"
        f"- logical_thinking (0-100 orasida son: mantiqiy fikrlash darajasi)\n"
        f"- logical_thinking_desc (1 jumlali qisqa tavsif)\n"
        f"- technical_level (0-100 orasida son: texnik daraja)\n"
        f"- technical_level_desc (1 jumlali qisqa tavsif)\n"
        f"- communication_level (0-100 orasida son: muloqot darajasi)\n"
        f"- communication_level_desc (1 jumlali qisqa tavsif)\n"
        f"- creativity_level (0-100 orasida son: kreativlik darajasi)\n"
        f"- creativity_level_desc (1 jumlali qisqa tavsif)\n"
        f"Faqat JSON qaytaring, boshqa hech narsa yozmang."
    )

    content = call_ollama(prompt)
    try:
        if content and "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif content and "```" in content:
            content = content.split("```")[1].split("```")[0]
        profile_data = json.loads(content.strip()) if content else {}
    except Exception:
        profile_data = {"summary": "Tahlil kutilmoqda..."}

    user.psychological_profile = profile_data
    user.save()
    return Response({'status': 'success', 'profile': profile_data})


# ─── Shared helper: parse Ollama JSON response ───────────────────────────────

def _parse_json(content):
    if not content:
        return None
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    try:
        return json.loads(content.strip())
    except Exception:
        return None


def _build_user_context(onboarding_data, profile, iq_score):
    interests = onboarding_data.get('interests', [])
    skills = onboarding_data.get('skills_to_develop', [])
    strengths = profile.get('strengths', [])
    return (
        f"- Ism: {onboarding_data.get('name', '')} {onboarding_data.get('surname', '')}\n"
        f"- Kasb: {onboarding_data.get('occupation', '')}\n"
        f"- Ta'lim: {onboarding_data.get('education_level', '')}\n"
        f"- Qiziqishlar: {', '.join(interests)}\n"
        f"- Ko'nikmalar: {', '.join(skills)}\n"
        f"- Orzusi: {onboarding_data.get('dream_career', '')}\n"
        f"- Kunlik o'qish vaqti: {onboarding_data.get('daily_study_time', '')}\n"
        f"- Maqsad: {onboarding_data.get('main_goal', '')}\n"
        f"- 5 yillik maqsad: {onboarding_data.get('five_year_vision', '')}\n"
        f"- IQ bali: {iq_score}\n"
        f"- Shaxsiyat: {profile.get('personality_type', '')}\n"
        f"- Kuchli tomonlar: {', '.join(strengths)}\n"
    )


# ─── Generate Roadmap ────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_roadmap_generate(request):
    import datetime
    user = request.user
    onboarding_data = user.onboarding_data or {}
    profile = user.psychological_profile or {}
    iq_score = user.iq_score or 0
    instruction = request.data.get('instruction', '').strip()

    # If there's an existing weekly plan, include week_goal as context for week 1
    existing_weekly = user.weekly_plan or {}
    weekly_context = ""
    if existing_weekly.get('week_goal'):
        weekly_context = (
            f"\nDiqqat: Foydalanuvchining joriy haftalik rejasi allaqachon mavjud. "
            f"1-haftani shu maqsad bilan moslashtir: \"{existing_weekly['week_goal']}\"\n"
        )

    extra = f"\nQo'shimcha ko'rsatma (MUHIM): {instruction}" if instruction else ""

    prompt = (
        f"Foydalanuvchi ma'lumotlari:\n"
        f"{_build_user_context(onboarding_data, profile, iq_score)}"
        f"{weekly_context}"
        f"{extra}\n\n"
        f"Ushbu foydalanuvchi uchun 8 haftalik shaxsiylashtirilgan o'quv yo'l xaritasini JSON formatda yarat.\n"
        f"MUHIM: 1-hafta joriy haftalik reja bilan mutanosib bo'lsin.\n"
        f"Tuzilma (faqat JSON):\n"
        f'{{"weeks": [{{"week": 1, "title": "...", "focus": "...", "topics": ["..."], "tasks": ["..."], "goal": "...", "resources": ["..."]}}]}}\n'
        f"8 ta hafta. Faqat JSON. O'zbek tilida."
    )

    content = call_ollama(prompt)
    roadmap_data = _parse_json(content) or {"weeks": []}

    # Sync: update weekly plan's week_goal from roadmap week 1
    updated_weekly = None
    weeks = roadmap_data.get('weeks', [])
    if weeks and user.weekly_plan:
        week1 = weeks[0]
        updated_weekly = dict(user.weekly_plan)
        updated_weekly['week_goal'] = week1.get('goal', updated_weekly.get('week_goal', ''))
        updated_weekly['week_focus'] = week1.get('focus', '')
        user.weekly_plan = updated_weekly

    # Save to chat history
    history = user.chat_history or []
    history.append({
        "type": "roadmap",
        "timestamp": datetime.datetime.now().isoformat(),
        "user_message": instruction if instruction else "Roadmap yaratildi",
        "ai_summary": f"{len(weeks)} haftalik yo'l xaritasi yaratildi"
    })
    user.chat_history = history
    user.roadmap = roadmap_data
    user.save()

    return Response({
        'status': 'success',
        'roadmap': roadmap_data,
        'weekly_plan': updated_weekly,  # None if no weekly existed
    })


# ─── Generate Weekly Plan ────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_weekly_generate(request):
    import datetime
    user = request.user
    onboarding_data = user.onboarding_data or {}
    profile = user.psychological_profile or {}
    iq_score = user.iq_score or 0
    instruction = request.data.get('instruction', '').strip()

    # Include roadmap week 1 as context so weekly stays consistent
    existing_roadmap = user.roadmap or {}
    weeks = existing_roadmap.get('weeks', [])
    roadmap_context = ""
    if weeks:
        w1 = weeks[0]
        roadmap_context = (
            f"\nDiqqat: Foydalanuvchining 8 haftalik yo'l xaritasida 1-hafta uchun:\n"
            f"- Sarlavha: {w1.get('title', '')}\n"
            f"- Yo'nalish: {w1.get('focus', '')}\n"
            f"- Maqsad: {w1.get('goal', '')}\n"
            f"- Mavzular: {', '.join(w1.get('topics', []))}\n"
            f"Haftalik reja shu bilan mutanosib bo'lsin.\n"
        )

    extra = f"\nQo'shimcha ko'rsatma (MUHIM, albatta hisobga ol): {instruction}" if instruction else ""

    # Build 7-day list starting from today
    days_uz = ['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba']
    today_idx = datetime.datetime.now().weekday()  # 0=Monday
    ordered_days = [days_uz[(today_idx + i) % 7] for i in range(7)]
    days_list = ', '.join(ordered_days)

    prompt = (
        f"Foydalanuvchi ma'lumotlari:\n"
        f"{_build_user_context(onboarding_data, profile, iq_score)}"
        f"{roadmap_context}"
        f"{extra}\n\n"
        f"Ushbu hafta uchun batafsil kunlik o'quv rejasini JSON formatda yarat.\n"
        f"MUHIM: Reja bugundan ({ordered_days[0]}) boshlanib, ketma-ket 7 kun davom etsin: {days_list}.\n"
        f"Har kun aniq, bajarilishi mumkin bo'lgan vazifalar bo'lsin.\n"
        f"Tuzilma (faqat JSON):\n"
        f'{{"week_goal": "...", "days": [{{"day": "Dushanba", "day_en": "monday", "theme": "...", "morning": "...", "afternoon": "...", "evening": "...", "tip": "..."}}]}}\n'
        f"Aynan {days_list} kunlari uchun yoz. Faqat JSON. O'zbek tilida."
    )

    content = call_ollama(prompt)
    weekly_data = _parse_json(content) or {"days": []}
    if 'days' not in weekly_data:
        weekly_data['days'] = []

    # Sync: update roadmap week 1 to match the new weekly plan
    updated_roadmap = None
    if weeks and weekly_data.get('week_goal'):
        updated_roadmap = dict(existing_roadmap)
        updated_weeks = list(weeks)
        updated_weeks[0] = dict(updated_weeks[0])
        updated_weeks[0]['goal'] = weekly_data['week_goal']
        # Update topics from weekly themes
        day_themes = [d.get('theme', '') for d in weekly_data.get('days', []) if d.get('theme')]
        if day_themes:
            updated_weeks[0]['topics'] = day_themes[:3]
        updated_roadmap['weeks'] = updated_weeks
        user.roadmap = updated_roadmap

    # Save to chat history
    history = user.chat_history or []
    history.append({
        "type": "weekly",
        "timestamp": datetime.datetime.now().isoformat(),
        "user_message": instruction if instruction else "Haftalik reja yaratildi",
        "ai_summary": f"{len(weekly_data.get('days', []))} kunlik haftalik reja yaratildi"
    })
    user.chat_history = history
    user.weekly_plan = weekly_data
    user.save()

    return Response({
        'status': 'success',
        'weekly_plan': weekly_data,
        'roadmap': updated_roadmap,  # None if no roadmap existed
    })


# ─── Generate Daily Plan ─────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_daily_generate(request):
    import datetime
    user = request.user
    onboarding_data = user.onboarding_data or {}
    profile = user.psychological_profile or {}
    iq_score = user.iq_score or 0
    instruction = request.data.get('instruction', '').strip()

    days_uz = ['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba']
    today_name = days_uz[datetime.datetime.now().weekday()]
    today_date = datetime.date.today().strftime('%d.%m.%Y')

    # Get today's entry from weekly plan as base context
    weekly = user.weekly_plan or {}
    weekly_today = None
    for d in weekly.get('days', []):
        if d.get('day', '').strip().lower() == today_name.lower():
            weekly_today = d
            break

    weekly_context = ""
    if weekly_today:
        weekly_context = (
            f"\nHaftalik rejada bugun uchun:\n"
            f"- Mavzu: {weekly_today.get('theme','')}\n"
            f"- Ertalab: {weekly_today.get('morning','')}\n"
            f"- Kunduzi: {weekly_today.get('afternoon','')}\n"
            f"- Kechqurun: {weekly_today.get('evening','')}\n"
        )

    extra = f"\nQo'shimcha ko'rsatma: {instruction}" if instruction else ""

    prompt = (
        f"Foydalanuvchi ma'lumotlari:\n"
        f"{_build_user_context(onboarding_data, profile, iq_score)}"
        f"{weekly_context}"
        f"{extra}\n\n"
        f"Bugun {today_name}, {today_date}. Ushbu foydalanuvchi uchun bugungi kunning batafsil soatma-soat o'quv rejasini JSON formatda yarat.\n"
        f"Reja amaliy, aniq va bajarilishi mumkin bo'lsin. Har bir blok uchun qisqa tavsif ber.\n"
        f"Tuzilma (faqat JSON):\n"
        f'{{\n'
        f'  "date": "{today_date}",\n'
        f'  "day": "{today_name}",\n'
        f'  "theme": "Bugungi asosiy mavzu",\n'
        f'  "goal": "Bugungi maqsad (1 jumla)",\n'
        f'  "motivational_quote": "Qisqa motivatsion ibora",\n'
        f'  "blocks": [\n'
        f'    {{\n'
        f'      "time": "08:00 - 09:00",\n'
        f'      "title": "Blok nomi",\n'
        f'      "type": "study",\n'
        f'      "description": "Nima qilish kerak (aniq)",\n'
        f'      "duration_min": 60\n'
        f'    }}\n'
        f'  ]\n'
        f'}}\n'
        f"type qiymatlari: study, practice, break, review, exercise\n"
        f"6-8 ta blok yoz (ertalabdan kechgacha). Faqat JSON. O'zbek tilida."
    )

    content = call_ollama(prompt)
    daily_data = _parse_json(content) or {}
    if 'blocks' not in daily_data:
        daily_data['blocks'] = []

    user.daily_plan = daily_data
    user.save()
    return Response({'status': 'success', 'daily_plan': daily_data})


# ─── Study Tracks ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_tracks_list(request):
    tracks = StudyTrack.objects.filter(user=request.user)
    data = [{'id': t.id, 'title': t.title, 'icon': t.icon, 'description': t.description,
             'has_daily': bool(t.daily_plan), 'has_weekly': bool(t.weekly_plan),
             'has_roadmap': bool(t.roadmap), 'created_at': t.created_at.isoformat()} for t in tracks]
    return Response({'status': 'success', 'tracks': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_track_create(request):
    import datetime
    title = request.data.get('title', '').strip()
    icon = request.data.get('icon', '📚').strip() or '📚'
    description = request.data.get('description', '').strip()
    if not title:
        return Response({'detail': 'title talab qilinadi'}, status=400)

    track = StudyTrack.objects.create(user=request.user, title=title, icon=icon, description=description)
    user = request.user
    ctx = _track_prompt_context(track, user)

    # 1. Roadmap
    roadmap_prompt = (
        f"{ctx}\n"
        f"Ushbu mashg'ulot bo'yicha 8 haftalik o'quv yo'l xaritasini JSON formatda yarat.\n"
        f"Tuzilma: {{\"weeks\":[{{\"week\":1,\"title\":\"...\",\"focus\":\"...\","
        f"\"topics\":[\"...\"],\"tasks\":[\"...\"],\"goal\":\"...\",\"resources\":[\"...\"]}}]}}\n"
        f"8 hafta. Faqat JSON. O'zbek tilida."
    )
    roadmap_data = _parse_json(call_ollama(roadmap_prompt)) or {'weeks': []}
    track.roadmap = roadmap_data

    # 2. Weekly (bugundan boshlab, roadmap week 1 konteksti bilan)
    days_uz = ['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba']
    today_idx = datetime.datetime.now().weekday()
    ordered_days = [days_uz[(today_idx + i) % 7] for i in range(7)]
    days_list = ', '.join(ordered_days)
    w1_ctx = ""
    if roadmap_data.get('weeks'):
        w1 = roadmap_data['weeks'][0]
        w1_ctx = f"\nRoadmap 1-hafta: {w1.get('focus','')} — {w1.get('goal','')}\n"
    weekly_prompt = (
        f"{ctx}{w1_ctx}\n"
        f"{days_list} kunlari uchun haftalik rejani JSON formatda yarat.\n"
        f"Tuzilma: {{\"week_goal\":\"...\","
        f"\"days\":[{{\"day\":\"Dushanba\",\"day_en\":\"monday\",\"theme\":\"...\","
        f"\"morning\":\"...\",\"afternoon\":\"...\",\"evening\":\"...\",\"tip\":\"...\"}}]}}\n"
        f"Aynan {days_list} kunlari. Faqat JSON. O'zbek tilida."
    )
    weekly_data = _parse_json(call_ollama(weekly_prompt)) or {'days': []}
    if 'days' not in weekly_data:
        weekly_data['days'] = []
    track.weekly_plan = weekly_data

    # 3. Daily (bugungi kun, haftalik konteksti bilan)
    today_name = days_uz[today_idx]
    today_date = datetime.date.today().strftime('%d.%m.%Y')
    today_entry = next((d for d in weekly_data.get('days', [])
                        if d.get('day','').lower() == today_name.lower()), None)
    daily_ctx = ""
    if today_entry:
        daily_ctx = (f"\nHaftalik rejada bugun: mavzu={today_entry.get('theme','')}, "
                     f"ertalab={today_entry.get('morning','')}, "
                     f"kunduzi={today_entry.get('afternoon','')}\n")
    daily_prompt = (
        f"{ctx}{daily_ctx}\n"
        f"Bugun {today_name}, {today_date}. Bugunning soatma-soat rejasini JSON formatda yarat.\n"
        f"Tuzilma: {{\"date\":\"{today_date}\",\"day\":\"{today_name}\",\"theme\":\"...\",\"goal\":\"...\","
        f"\"motivational_quote\":\"...\","
        f"\"blocks\":[{{\"time\":\"08:00-09:00\",\"title\":\"...\",\"type\":\"study\","
        f"\"description\":\"...\",\"duration_min\":60}}]}}\n"
        f"type: study/practice/break/review/exercise. 6-8 blok. Faqat JSON. O'zbek tilida."
    )
    daily_data = _parse_json(call_ollama(daily_prompt)) or {'blocks': []}
    if 'blocks' not in daily_data:
        daily_data['blocks'] = []
    track.daily_plan = daily_data

    track.save()
    return Response({'status': 'success', 'track': {
        'id': track.id, 'title': track.title, 'icon': track.icon,
        'description': track.description,
        'daily_plan': daily_data,
        'weekly_plan': weekly_data,
        'roadmap': roadmap_data,
        'has_daily': True, 'has_weekly': True, 'has_roadmap': True,
        'created_at': track.created_at.isoformat(),
    }})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_track_delete(request, track_id):
    try:
        track = StudyTrack.objects.get(id=track_id, user=request.user)
        track.delete()
        return Response({'status': 'success'})
    except StudyTrack.DoesNotExist:
        return Response({'detail': 'Topilmadi'}, status=404)


def _track_prompt_context(track, user):
    od = user.onboarding_data or {}
    profile = user.psychological_profile or {}
    return (
        f"Mashg'ulot: {track.icon} {track.title}\n"
        f"{'Tavsif: ' + track.description + chr(10) if track.description else ''}"
        f"O'quvchi: {od.get('name','')} {od.get('surname','')}, {od.get('occupation','')}\n"
        f"Qiziqishlar: {', '.join(od.get('interests',[]))}\n"
        f"Kunlik o'qish vaqti: {od.get('daily_study_time','')}\n"
        f"Shaxsiyat: {profile.get('personality_type','')}\n"
        f"IQ: {user.iq_score}\n"
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_track_daily(request, track_id):
    import datetime
    try:
        track = StudyTrack.objects.get(id=track_id, user=request.user)
    except StudyTrack.DoesNotExist:
        return Response({'detail': 'Topilmadi'}, status=404)

    instruction = request.data.get('instruction', '').strip()
    days_uz = ['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba']
    today_name = days_uz[datetime.datetime.now().weekday()]
    today_date = datetime.date.today().strftime('%d.%m.%Y')
    extra = f"\nQo'shimcha: {instruction}" if instruction else ""

    prompt = (
        f"{_track_prompt_context(track, request.user)}"
        f"{extra}\n\n"
        f"Bugun {today_name}, {today_date}. Ushbu mashg'ulot bo'yicha bugunning soatma-soat rejasini JSON formatda yarat.\n"
        f"Tuzilma: {{\"date\":\"{today_date}\",\"day\":\"{today_name}\",\"theme\":\"...\",\"goal\":\"...\","
        f"\"motivational_quote\":\"...\","
        f"\"blocks\":[{{\"time\":\"08:00-09:00\",\"title\":\"...\",\"type\":\"study\",\"description\":\"...\",\"duration_min\":60}}]}}\n"
        f"type: study/practice/break/review/exercise. 6-8 blok. Faqat JSON. O'zbek tilida."
    )
    daily_data = _parse_json(call_ollama(prompt)) or {'blocks': []}
    track.daily_plan = daily_data
    track.save()
    return Response({'status': 'success', 'daily_plan': daily_data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_track_weekly(request, track_id):
    import datetime
    try:
        track = StudyTrack.objects.get(id=track_id, user=request.user)
    except StudyTrack.DoesNotExist:
        return Response({'detail': 'Topilmadi'}, status=404)

    instruction = request.data.get('instruction', '').strip()
    days_uz = ['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba']
    today_idx = datetime.datetime.now().weekday()
    ordered_days = [days_uz[(today_idx + i) % 7] for i in range(7)]
    days_list = ', '.join(ordered_days)
    extra = f"\nQo'shimcha: {instruction}" if instruction else ""

    # Sync with roadmap week 1 if exists
    roadmap_ctx = ""
    if track.roadmap and track.roadmap.get('weeks'):
        w1 = track.roadmap['weeks'][0]
        roadmap_ctx = f"\nRoadmap 1-hafta: {w1.get('focus','')} — {w1.get('goal','')}\n"

    prompt = (
        f"{_track_prompt_context(track, request.user)}"
        f"{roadmap_ctx}{extra}\n\n"
        f"Ushbu mashg'ulot bo'yicha {days_list} kunlari uchun haftalik rejani JSON formatda yarat.\n"
        f"Tuzilma: {{\"week_goal\":\"...\","
        f"\"days\":[{{\"day\":\"Dushanba\",\"day_en\":\"monday\",\"theme\":\"...\","
        f"\"morning\":\"...\",\"afternoon\":\"...\",\"evening\":\"...\",\"tip\":\"...\"}}]}}\n"
        f"Aynan {days_list} kunlari. Faqat JSON. O'zbek tilida."
    )
    weekly_data = _parse_json(call_ollama(prompt)) or {'days': []}
    if 'days' not in weekly_data:
        weekly_data['days'] = []

    # Sync week 1 of roadmap
    if track.roadmap and weekly_data.get('week_goal') and track.roadmap.get('weeks'):
        track.roadmap['weeks'][0]['goal'] = weekly_data['week_goal']

    track.weekly_plan = weekly_data
    track.save()
    return Response({'status': 'success', 'weekly_plan': weekly_data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_track_roadmap(request, track_id):
    import datetime
    try:
        track = StudyTrack.objects.get(id=track_id, user=request.user)
    except StudyTrack.DoesNotExist:
        return Response({'detail': 'Topilmadi'}, status=404)

    instruction = request.data.get('instruction', '').strip()
    extra = f"\nQo'shimcha: {instruction}" if instruction else ""
    weekly_ctx = ""
    if track.weekly_plan and track.weekly_plan.get('week_goal'):
        weekly_ctx = f"\nJoriy haftalik maqsad: {track.weekly_plan['week_goal']}\n"

    prompt = (
        f"{_track_prompt_context(track, request.user)}"
        f"{weekly_ctx}{extra}\n\n"
        f"Ushbu mashg'ulot bo'yicha 8 haftalik o'quv yo'l xaritasini JSON formatda yarat.\n"
        f"Tuzilma: {{\"weeks\":[{{\"week\":1,\"title\":\"...\",\"focus\":\"...\","
        f"\"topics\":[\"...\"],\"tasks\":[\"...\"],\"goal\":\"...\",\"resources\":[\"...\"]}}]}}\n"
        f"8 hafta. Faqat JSON. O'zbek tilida."
    )
    roadmap_data = _parse_json(call_ollama(prompt)) or {'weeks': []}

    # Sync weekly week_goal from roadmap week 1
    updated_weekly = None
    if roadmap_data.get('weeks') and track.weekly_plan:
        track.weekly_plan['week_goal'] = roadmap_data['weeks'][0].get('goal', track.weekly_plan.get('week_goal',''))
        updated_weekly = track.weekly_plan

    track.roadmap = roadmap_data
    track.save()
    return Response({'status': 'success', 'roadmap': roadmap_data, 'weekly_plan': updated_weekly})


# ─── Chatbot ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_chatbot_message(request):
    import datetime
    user = request.user
    user_message = request.data.get('message', '').strip()
    if not user_message:
        return Response({'detail': 'message talab qilinadi'}, status=400)

    # Detect today's day plan from weekly_plan
    weekly = user.weekly_plan or {}
    days_uz = ['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba']
    today_idx = datetime.datetime.now().weekday()  # 0=Monday
    today_name = days_uz[today_idx]
    today_plan = None
    for d in weekly.get('days', []):
        if d.get('day', '').strip().lower() == today_name.lower():
            today_plan = d
            break

    # Build system prompt
    if today_plan:
        plan_text = (
            f"Bugun {today_name}. Foydalanuvchining bugungi o'quv rejasi:\n"
            f"- Mavzu: {today_plan.get('theme', '—')}\n"
            f"- Ertalab: {today_plan.get('morning', '—')}\n"
            f"- Kunduzi: {today_plan.get('afternoon', '—')}\n"
            f"- Kechqurun: {today_plan.get('evening', '—')}\n"
            f"- Maslahat: {today_plan.get('tip', '—')}\n"
        )
    else:
        plan_text = f"Bugun {today_name}. Foydalanuvchining haftalik rejasi hali yuklanmagan."

    week_goal = weekly.get('week_goal', '')
    name = (user.onboarding_data or {}).get('name', 'do\'stim')

    system_prompt = (
        f"Sen HamrohAI — {name}ning shaxsiy AI o'quv yordamchisi.\n\n"
        f"{plan_text}\n"
        f"{'Haftaning maqsadi: ' + week_goal if week_goal else ''}\n\n"
        f"Qoidalar:\n"
        f"1. Suhbatni DOIM bugungi reja mavzulariga yo'nalt. Foydalanuvchini bugungi vazifalarini bajarishga undash.\n"
        f"2. Agar foydalanuvchi rejadan TASHQARI savol bersa — qisqacha javob ber, so'ng muloyimlik bilan rejaga qaytishni eslatib, bugungi mavzuga undab so'ra.\n"
        f"3. Javoblar qisqa (2-4 jumla), do'stona, motivatsion bo'lsin.\n"
        f"4. O'zbek tilida gaplash.\n"
        f"5. Foydalanuvchi biror mavzuni tushunmasa — oddiy tilda tushuntir va misol kel.\n"
        f"6. Hech qachon reja mavzusidan uzoqlashma."
    )

    # Load conversation history (last 10 messages)
    history = user.chatbot_history or []
    recent = history[-10:] if len(history) > 10 else history

    # Build messages for Ollama
    messages = [{"role": "system", "content": system_prompt}]
    for h in recent:
        messages.append({"role": h['role'], "content": h['content']})
    messages.append({"role": "user", "content": user_message})

    # Call Ollama with full message history
    reply = call_ollama(user_message, messages[:-1], system=system_prompt)
    if not reply:
        reply = "Kechirasiz, hozir javob bera olmayapman. Biroz kutib qayta urinib ko'ring."

    # Save to chatbot history
    history.append({"role": "user", "content": user_message,
                    "timestamp": datetime.datetime.now().isoformat()})
    history.append({"role": "assistant", "content": reply,
                    "timestamp": datetime.datetime.now().isoformat()})
    user.chatbot_history = history
    user.save()

    return Response({'status': 'success', 'reply': reply, 'today_plan': today_plan})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_chatbot_reset(request):
    request.user.chatbot_history = []
    request.user.save()
    return Response({'status': 'success'})


# ─── Save IQ score ────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_save_iq(request):
    iq_score = request.data.get('iqScore', 0)
    user = request.user
    user.iq_score = iq_score
    user.onboarding_completed = True
    user.save()
    return Response({'status': 'success', 'iqScore': iq_score})
