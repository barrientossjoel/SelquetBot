"""Selector del proveedor de WhatsApp.

Configurar con `WHATSAPP_PROVIDER=meta|twilio` (default: meta, porque el número
de prueba de la guía es de Meta). Twilio queda como fallback.
"""
import os

from .base import WhatsAppProvider
from .meta import MetaProvider
from .twilio import TwilioProvider

_provider = None


def get_provider() -> WhatsAppProvider:
    global _provider
    if _provider is None:
        name = (os.getenv('WHATSAPP_PROVIDER', 'meta') or 'meta').lower()
        _provider = TwilioProvider() if name == 'twilio' else MetaProvider()
    return _provider


def reset_provider():
    """Olvida el provider cacheado (para tests o cambios de env en runtime)."""
    global _provider
    _provider = None


__all__ = ['WhatsAppProvider', 'get_provider', 'reset_provider']
