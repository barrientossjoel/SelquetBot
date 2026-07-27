"""Rutas del webhook de WhatsApp. El transporte (Meta/Twilio) está abstraído
en whatsapp.providers.
"""
import sys
import traceback

from flask import Blueprint, request

from .message_processor import handle_incoming_message_async
from .providers import get_provider

whatsapp_bp = Blueprint('whatsapp', __name__)


@whatsapp_bp.route('/webhook/whatsapp', methods=['GET'])
def webhook_verify():
    """Challenge de verificación de Meta. Twilio no usa GET → responde 200."""
    return get_provider().handle_verify_get(request) or ('OK', 200)


@whatsapp_bp.route('/webhook/whatsapp', methods=['POST'])
def webhook_receive():
    """Recibe mensajes entrantes y los despacha en thread separado.
    Meta/Twilio exigen un 200 rápido, por eso el procesamiento es async."""
    provider = get_provider()

    if not provider.verify_signature(request):
        print('[SELQUET WEBHOOK] Firma inválida — rechazado', flush=True)
        return 'Forbidden', 403

    try:
        mensajes = provider.parse_webhook(request)
        print(f"[SELQUET WEBHOOK] {len(mensajes)} mensajes recibidos", flush=True)
        sys.stdout.flush()
        for telefono, message, contacts in mensajes:
            print(f"[SELQUET WEBHOOK] {telefono}: {message.get('type')}", flush=True)
            handle_incoming_message_async(telefono, message, contacts)
    except Exception as ex:
        print(f"[SELQUET] Error procesando webhook: {ex}", flush=True)
        traceback.print_exc()

    return 'OK', 200
