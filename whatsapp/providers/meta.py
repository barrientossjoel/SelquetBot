"""Adapter para Meta WhatsApp Cloud API (Graph API v21.0).

Proveedor principal del MVP: el número de prueba de Meta for Developers es
gratis y no requiere verificar el negocio.
"""
import os

import requests

from .base import WhatsAppProvider

API_URL = 'https://graph.facebook.com/v21.0'


class MetaProvider(WhatsAppProvider):

    def __init__(self):
        self.api_token = os.getenv('WHATSAPP_API_TOKEN', '')
        self.phone_number_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
        self.verify_token = os.getenv('WHATSAPP_VERIFY_TOKEN', '')

    def handle_verify_get(self, request):
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == self.verify_token:
            print('[WhatsApp Meta] Webhook verificado')
            return challenge, 200
        print('[WhatsApp Meta] Verificación fallida')
        return 'Forbidden', 403

    def verify_signature(self, request) -> bool:
        # El número de prueba de Meta no firma con X-Hub-Signature; se valida
        # con el verify_token en el GET. En producción se agregaría la firma.
        return True

    def parse_webhook(self, request):
        body = request.get_json(silent=True) or {}
        result = []
        for entry in body.get('entry', []):
            for change in entry.get('changes', []):
                value = change.get('value', {})
                contacts = value.get('contacts', [])
                for message in value.get('messages', []):
                    telefono = message.get('from', '')
                    if telefono:
                        result.append((telefono, message, contacts))
        return result

    def send_message(self, telefono, texto):
        if not self.api_token or not self.phone_number_id:
            print(f"[WhatsApp Meta] (sin credenciales) → {telefono}: {texto}")
            return True
        return self._post({
            'messaging_product': 'whatsapp',
            'to': _normalizar_telefono_ar(telefono),
            'type': 'text',
            'text': {'body': texto},
        })

    def send_document(self, telefono, link, filename='documento.pdf', caption=''):
        if not self.api_token or not self.phone_number_id:
            print(f"[WhatsApp Meta] (sin credenciales) → documento a {telefono}: {link}")
            return True
        documento = {'link': link, 'filename': filename}
        if caption:
            documento['caption'] = caption
        return self._post({
            'messaging_product': 'whatsapp',
            'to': _normalizar_telefono_ar(telefono),
            'type': 'document',
            'document': documento,
        })

    def _post(self, payload):
        url = f"{API_URL}/{self.phone_number_id}/messages"
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                # El token de prueba vence cada 24h → un 401 acá suele ser eso.
                print(f"[WhatsApp Meta] Error enviando: {response.status_code} - {response.text}")
                return False
            return True
        except Exception as e:
            print(f"[WhatsApp Meta] Error de red: {e}")
            return False


def _normalizar_telefono_ar(telefono):
    """Meta envía 5491128366833 pero espera 541128366833 para responder."""
    if telefono.startswith('549') and len(telefono) >= 12:
        return '54' + telefono[3:]
    return telefono
