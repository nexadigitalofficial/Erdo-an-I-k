import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'smtp').strip().lower()
EMAIL_FROM = os.environ.get('EMAIL_FROM', '').strip()
EMAIL_FROM_NAME = os.environ.get('EMAIL_FROM_NAME', 'Nexa CRM').strip()

# SMTP config
SMTP_HOST = os.environ.get('SMTP_HOST', '').strip()
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587') or 587)
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '').strip()
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '').strip()
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').strip().lower() in ('1', 'true', 'yes')

# Resend config
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '').strip()
RESEND_API_URL = 'https://api.resend.com/emails'


def email_status() -> dict:
    smtp_ok = bool(EMAIL_FROM and SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD)
    resend_ok = bool(EMAIL_FROM and RESEND_API_KEY)
    configured = resend_ok if EMAIL_PROVIDER == 'resend' else smtp_ok
    return {
        'ok': configured,
        'configured': configured,
        'provider': EMAIL_PROVIDER,
        'from': EMAIL_FROM,
        'smtp_ready': smtp_ok,
        'resend_ready': resend_ok,
    }



def _build_html_wrapper(title: str, body_html: str) -> str:
    return f'''<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#0b0f19;font-family:Arial,Helvetica,sans-serif;color:#e5e7eb;">
  <div style="max-width:640px;margin:0 auto;padding:32px 20px;">
    <div style="background:#121826;border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:32px;">
      <div style="font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:#c7a34b;margin-bottom:14px;">Nexa CRM</div>
      {body_html}
      <div style="margin-top:28px;padding-top:18px;border-top:1px solid rgba(255,255,255,.08);font-size:12px;color:#9ca3af;line-height:1.7;">
        Bu e-posta otomatik olarak oluşturulmuştur. Ek sorularınız için bu mesaja yanıt verebilir veya bizimle telefon üzerinden iletişime geçebilirsiniz.
      </div>
    </div>
  </div>
</body>
</html>'''



def build_lead_confirmation_email(name: str, phone: str = '', neighborhood: str = '', property_type: str = '', notes: str = '') -> tuple[str, str, str]:
    subject = 'Talebiniz bize ulaştı'
    plain = (
        f'Merhaba {name},\n\n'
        'Talebiniz bize başarıyla ulaştı. En kısa sürede sizinle iletişime geçeceğiz.\n\n'
        + (f'Mahalle: {neighborhood}\n' if neighborhood else '')
        + (f'Mülk Tipi: {property_type}\n' if property_type else '')
        + (f'Telefon: {phone}\n' if phone else '')
        + (f'Notunuz: {notes}\n' if notes else '')
        + '\nTeşekkür ederiz.\nNexa CRM'
    )
    html_body = f'''
      <h1 style="margin:0 0 12px;font-size:28px;line-height:1.2;color:#ffffff;">Merhaba {name},</h1>
      <p style="margin:0 0 18px;font-size:16px;line-height:1.7;color:#d1d5db;">
        Talebiniz bize başarıyla ulaştı. Ekibimiz en kısa sürede sizinle iletişime geçecek.
      </p>
      <div style="background:#0f172a;border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px 18px 8px;margin:18px 0;">
        <div style="font-size:14px;color:#f3f4f6;font-weight:bold;margin-bottom:10px;">Talep Özeti</div>
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Mahalle:</strong> {neighborhood}</p>' if neighborhood else ''}
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Mülk Tipi:</strong> {property_type}</p>' if property_type else ''}
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Telefon:</strong> {phone}</p>' if phone else ''}
        {f'<p style="margin:0 0 10px;color:#cbd5e1;"><strong>Notunuz:</strong> {notes}</p>' if notes else ''}
      </div>
      <p style="margin:0;font-size:15px;line-height:1.7;color:#d1d5db;">
        Dilerseniz bu e-postayı yanıtlayarak ek bilgi paylaşabilirsiniz.
      </p>
    '''
    return subject, plain, _build_html_wrapper(subject, html_body)



def _send_via_smtp(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    if not (EMAIL_FROM and SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD):
        return {'ok': False, 'error': 'SMTP yapılandırması eksik'}

    msg = MIMEMultipart('alternative') if html_body else MIMEText(text_body, 'plain', 'utf-8')
    if html_body:
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg['Subject'] = subject
    msg['From'] = formataddr((EMAIL_FROM_NAME, EMAIL_FROM))
    msg['To'] = to_email

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [to_email], msg.as_string())
        return {'ok': True, 'provider': 'smtp', 'to': to_email}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'provider': 'smtp'}



def _send_via_resend(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    if not (EMAIL_FROM and RESEND_API_KEY):
        return {'ok': False, 'error': 'Resend yapılandırması eksik'}
    payload = {
        'from': formataddr((EMAIL_FROM_NAME, EMAIL_FROM)),
        'to': [to_email],
        'subject': subject,
        'text': text_body,
    }
    if html_body:
        payload['html'] = html_body
    try:
        resp = requests.post(
            RESEND_API_URL,
            headers={'Authorization': f'Bearer {RESEND_API_KEY}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=15,
        )
        data = resp.json() if resp.content else {}
        if resp.ok:
            return {'ok': True, 'provider': 'resend', 'to': to_email, 'id': data.get('id', '')}
        return {'ok': False, 'error': data.get('message', str(data)), 'provider': 'resend'}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'provider': 'resend'}



def send_transactional_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> dict:
    if not to_email:
        return {'ok': False, 'error': 'Alıcı e-posta boş'}
    provider = EMAIL_PROVIDER
    if provider == 'resend':
        return _send_via_resend(to_email, subject, text_body, html_body)
    return _send_via_smtp(to_email, subject, text_body, html_body)
