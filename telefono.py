"""Normalización de teléfonos argentinos, compartida entre el panel y la web.

Deja el número en formato internacional sin '+': '1156194427' → '5491156194427'.
Sirve tanto para enviar por la API de WhatsApp como para armar links wa.me.
"""
from __future__ import annotations


def normalizar_ar(numero: str | None) -> str | None:
    """'11 5619-4427' → '5491156194427'; '011 5619-4427' → '5491156194427'.
    Devuelve None si no hay dígitos. Saca el 0 nacional (011 → 11) y el 15 de los
    celulares para no armar números inválidos que WhatsApp rechaza."""
    d = ''.join(c for c in (numero or '') if c.isdigit())
    if not d:
        return None
    if d.startswith('54'):
        return d
    d = d.lstrip('0')          # 011... → 11...  (saca el 0 de discado nacional)
    return '549' + _sin_15(d)


def _sin_15(d: str) -> str:
    """'351 15 456-7890' → '3514567890'. El 15 se escribe justo después del código
    de área (2 a 4 dígitos) y suma 2 dígitos de más, así que solo se saca cuando el
    número queda en los 10 dígitos de un celular argentino."""
    if len(d) != 12:
        return d
    for area in (2, 3, 4):
        if d[area:area + 2] == '15':
            return d[:area] + d[area + 2:]
    return d
