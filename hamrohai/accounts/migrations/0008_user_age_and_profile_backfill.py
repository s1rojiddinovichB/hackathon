import datetime

from django.db import migrations, models


def _extract_age(onboarding_data):
    if not onboarding_data:
        return 0

    explicit_age = onboarding_data.get('age')
    if explicit_age not in (None, ''):
        try:
            return max(int(explicit_age), 0)
        except (TypeError, ValueError):
            pass

    birth_date = onboarding_data.get('birth_date')
    if not birth_date:
        return 0

    try:
        parsed = datetime.date.fromisoformat(str(birth_date))
    except (TypeError, ValueError):
        return 0

    today = datetime.date.today()
    return max(
        today.year - parsed.year - ((today.month, today.day) < (parsed.month, parsed.day)),
        0,
    )


def backfill_users_and_profiles(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    for user in User.objects.all():
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'provider': 'email',
                'onboarding_completed': False,
                'iq_score': 0,
            },
        )

        onboarding_data = dict(profile.onboarding_data or {})
        update_fields = []

        if not user.first_name and onboarding_data.get('name'):
            user.first_name = str(onboarding_data.get('name') or '').strip()
            update_fields.append('first_name')
        if not user.last_name and onboarding_data.get('surname'):
            user.last_name = str(onboarding_data.get('surname') or '').strip()
            update_fields.append('last_name')
        if not user.age:
            user.age = _extract_age(onboarding_data)
            update_fields.append('age')

        if update_fields:
            user.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='age',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_users_and_profiles, migrations.RunPython.noop),
    ]
