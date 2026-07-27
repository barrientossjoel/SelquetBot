"""Procesamiento de mensajes entrantes de WhatsApp.

- Dedup por id de mensaje (Meta reintenta los webhooks).
- Despacho en thread daemon para responder 200 rápido (<5s) y procesar aparte.
- Solo texto en el MVP; otros tipos reciben un aviso amable.
"""
from __future__ import annotations

import threading
import traceback
from collections import OrderedDict

import config_store
from . import chat_engine
from .providers import get_provider

# Dedup acotado: recordamos los últimos ids vistos.
_VISTOS: "OrderedDict[str, bool]" = OrderedDict()
_MAX_VISTOS = 500
_lock = threading.Lock()

MSG_NO_TEXTO = ("Por ahora solo puedo leer mensajes de texto 🙂 "
                "Escribime tu consulta y te respondo.")


def _ya_procesado(message_id: str) -> bool:
    """True si ya vimos ese id; si es nuevo, lo registra."""
    if not message_id:
        return False
    with _lock:
        if message_id in _VISTOS:
            return True
        _VISTOS[message_id] = True
        while len(_VISTOS) > _MAX_VISTOS:
            _VISTOS.popitem(last=False)
    return False


def handle_incoming_message(telefono, message, contacts=None):
    """Procesa un mensaje entrante y responde. Corre dentro de un thread."""
    provider = get_provider()

    if _ya_procesado(message.get('id', '')):
        print(f"[SELQUET] Mensaje duplicado ignorado ({telefono})", flush=True)
        return

    if not config_store.is_bot_activo():
        print(f"[SELQUET] Bot desactivado — no se responde a {telefono}", flush=True)
        return

    if message.get('type') != 'text':
        provider.send_message(telefono, MSG_NO_TEXTO)
        return

    texto = (message.get('text', {}) or {}).get('body', '').strip()
    if not texto:
        return

    respuesta = chat_engine.responder(telefono, texto)
    provider.send_message(telefono, respuesta)


def _safe_handle(telefono, message, contacts):
    try:
        print(f"[SELQUET] Procesando mensaje de {telefono}...", flush=True)
        handle_incoming_message(telefono, message, contacts)
    except Exception as e:
        print(f"[SELQUET] ERROR en thread para {telefono}: {e}", flush=True)
        traceback.print_exc()


def handle_incoming_message_async(telefono, message, contacts=None):
    threading.Thread(target=_safe_handle, args=(telefono, message, contacts), daemon=True).start()
