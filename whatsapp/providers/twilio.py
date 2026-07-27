"""Adapter para Twilio WhatsApp (fallback).

Webhook entrante: form-urlencoded con campos From, Body, ProfileName, etc.
Solo se usa si WHATSAPP_PROVIDER=twilio. Requiere cuenta y credenciales de Twilio.
"""
import os

from .base import WhatsAppProvider


class TwilioProvider(WhatsAppProvider):

    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID', '')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN', '')
        self.wa_from = os.getenv('TWILIO_WA_NUMBER', '')
        self._client = None
        self._validator = None

    @property
    def client(self):
        if self._client is None and self.account_sid and self.auth_token:
            from twilio.rest import Client
            self._client = Client(self.account_sid, self.auth_token)
        return self._client

    @property
    def validator(self):
        if self._validator is None and self.auth_token:
            from twilio.request_validator import RequestValidator
            self._validator = RequestValidator(self.auth_token)
        return self._validator

    def verify_signature(self, request) -> bool:
        if (os.getenv('TWILIO_VERIFY_SIGNATURE', 'true') or 'true').lower() == 'false':
            return True
        if not self.validator:
            return True
        signature = request.headers.get('X-Twilio-Signature', '')
        if not signature:
            return False
        proto = request.headers.get('X-Forwarded-Proto', request.scheme)
        path = request.full_path[:-1] if request.full_path.endswith('?') else request.full_path
        url = f"{proto}://{request.host}{path}"
        params = request.form.to_dict(flat=True)
        return self.validator.validate(url, params, signature)

    def parse_webhook(self, request):
        form = request.form
        telefono = _from_to_phone(form.get('From', ''))
        if not telefono:
            return []
        profile_name = (form.get('ProfileName') or '').strip()
        contacts = [{'profile': {'name': profile_name}}] if profile_name else []
        message = {
            'type': 'text',
            'from': telefono,
            'text': {'body': (form.get('Body') or '').strip()},
        }
        return [(telefono, message, contacts)]

    def send_message(self, telefono, texto):
        if not self.client or not self.wa_from:
            print(f"[Twilio] (sin credenciales) → {telefono}: {texto}")
            return True
        try:
            self.client.messages.create(
                from_=self.wa_from,
                to=f"whatsapp:+{telefono.lstrip('+')}",
                body=texto,
            )
            return True
        except Exception as e:
            print(f"[Twilio] Error enviando: {e}")
            return False


def _from_to_phone(from_raw: str) -> str:
    """'whatsapp:+5491176325106' → '5491176325106'"""
    if not from_raw:
        return ''
    return from_raw.replace('whatsapp:', '').lstrip('+').strip()
