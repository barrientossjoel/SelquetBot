"""Normalización de teléfonos argentinos, compartida entre el panel y la web.

Deja el número en formato internacional sin '+': '1156194427' → '5491156194427'.
Sirve tanto para enviar por la API de WhatsApp como para armar links wa.me.
"""
from __future__ import annotations


def normalizar_ar(numero: str | None) -> str | None:
    """'11 5619-4427' → '5491156194427'. Devuelve None si no hay dígitos."""
    digitos = ''.join(c for c in (numero or '') if c.isdigit())
    if not digitos:
        return None
    return digitos if digitos.startswith('54') else '549' + digitos
