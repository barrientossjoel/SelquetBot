"""Interfaz común para proveedores de WhatsApp.

Permite alternar entre Meta Cloud API y Twilio sin tocar la lógica de negocio.
El resto del módulo trabaja con un formato interno tipo Meta:

    {
        'type': 'text',
        'from': '5491176325106',
        'text': {'body': '...'},
    }

En el MVP solo procesamos texto; el formato queda abierto para media a futuro.
"""
from abc import ABC, abstractmethod


class WhatsAppProvider(ABC):

    @abstractmethod
    def parse_webhook(self, request):
        """Parsea el POST entrante. Retorna lista de tuplas (telefono, message, contacts)."""

    @abstractmethod
    def verify_signature(self, request) -> bool:
        """Valida la firma del webhook entrante."""

    @abstractmethod
    def send_message(self, telefono: str, texto: str) -> bool:
        """Envía un mensaje de texto."""

    def send_document(self, telefono: str, link: str, filename: str = 'documento.pdf', caption: str = '') -> bool:
        """Envía un documento (PDF) desde una URL pública. Default: no soportado."""
        print(f"[WhatsApp] send_document no soportado por {self.__class__.__name__}")
        return False

    def handle_verify_get(self, request):
        """Solo Meta usa GET para validar el webhook (challenge).
        Retorna (body, status) o None si el provider no lo soporta."""
        return None
