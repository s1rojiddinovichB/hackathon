import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings


def send_otp_email(to_email: str, code: str):
    smtp_email = getattr(settings, 'SMTP_EMAIL', '')
    smtp_password = getattr(settings, 'SMTP_APP_PASSWORD', '')

    if not smtp_email or not smtp_password:
        print(f"!!! DIQQAT !!! SMTP ishga tushmagan. {to_email} ga kod: {code}")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = to_email
        msg['Subject'] = "HamrohAi - Tasdiqlash Kodi"

        body = (
            f"Assalomu alaykum,\n\n"
            f"Sizning ro'yxatdan o'tish uchun tasdiqlash kodingiz: {code}\n\n"
            f"Bu kodni hech kimga bermang!\n"
            f"5 daqiqa ichida kiriting."
        )
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False


def call_ollama(prompt, messages=None, system=None):
    if messages is None:
        messages = []
    try:
        import ollama
        default_system = (
            "Sen insonlarga onboarding jarayonida yordam beruvchi xushmuomala, "
            "ochiqko'ngil botsan. Javoblaring juda qisqa bo'lsin."
        )
        full_messages = [{"role": "system", "content": system or default_system}]
        for m in messages:
            if m.get('role') != 'system':
                full_messages.append({"role": m['role'], "content": m['content']})
        full_messages.append({"role": "user", "content": prompt})

        model = getattr(settings, 'OLLAMA_MODEL', 'gemini-3-flash-preview:latest')
        response = ollama.chat(model=model, messages=full_messages)
        return response.get("message", {}).get("content", "")
    except Exception as e:
        print(f"Ollama Error: {e}")
        return None
