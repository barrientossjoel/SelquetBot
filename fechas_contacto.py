"""Fechas especiales de reservas: días en los que el local exige SÍ O SÍ un dato
de contacto (teléfono o email) para tomar una reserva.

El listado vive en la config del local (tabla clave-valor), así el local lo
edita desde el panel sin tocar código. Formato del valor: una fecha por línea,
`YYYY-MM-DD` con un motivo opcional después de `|`
(ej. `2026-10-18 | Día de la Madre`).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from config_store import get_config, set_config

CLAVE_CONFIG = 'fechas_contacto_obligatorio'
# Día de la Madre 2026: el local necesita poder llamar a cada mesa.
DEFAULT = '2026-10-18 | Día de la Madre'

ETIQUETA_DATO = 'un dato de contacto (teléfono o email)'
_MIN_DIGITOS_TEL = 8
_RE_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$')


def fechas() -> dict[date, str]:
    """`{fecha: motivo}` según la config. Las líneas inválidas se ignoran."""
    resultado: dict[date, str] = {}
    for linea in get_config(CLAVE_CONFIG, DEFAULT).splitlines():
        fecha_txt, _, motivo_txt = linea.partition('|')
        fecha = _a_fecha(fecha_txt)
        if fecha:
            resultado[fecha] = motivo_txt.strip()
    return resultado


def requiere_contacto(cuando: datetime | date | None) -> bool:
    """True si ese día el local exige el dato de contacto."""
    return _a_dia(cuando) in fechas()


def motivo(cuando: datetime | date | None) -> str:
    """Motivo configurado para ese día ('Día de la Madre'), o '' si no hay."""
    return fechas().get(_a_dia(cuando), '')


def contacto_valido(contacto: str | None) -> bool:
    """Acepta un email, o un teléfono con al menos 8 dígitos."""
    texto = (contacto or '').strip()
    if not texto:
        return False
    if '@' in texto:
        return bool(_RE_EMAIL.match(texto))
    return sum(c.isdigit() for c in texto) >= _MIN_DIGITOS_TEL


def texto_config() -> str:
    """Valor crudo para el textarea del panel."""
    return get_config(CLAVE_CONFIG, DEFAULT)


def guardar(texto: str) -> tuple[int, list[str]]:
    """Normaliza y guarda el listado. Si alguna línea no se entiende NO guarda nada
    (para no borrar sin querer las fechas ya cargadas).
    Devuelve (fechas guardadas, líneas inválidas)."""
    validas: list[str] = []
    invalidas: list[str] = []
    for linea in (texto or '').splitlines():
        if not linea.strip():
            continue
        fecha_txt, _, motivo_txt = linea.partition('|')
        fecha = _a_fecha(fecha_txt)
        if not fecha:
            invalidas.append(linea.strip())
            continue
        motivo_txt = motivo_txt.strip()
        validas.append(f'{fecha.isoformat()} | {motivo_txt}' if motivo_txt else fecha.isoformat())
    if invalidas:
        return 0, invalidas
    set_config({CLAVE_CONFIG: '\n'.join(validas)})
    return len(validas), []


def bloque_prompt() -> str:
    """Bloque para el prompt del bot con las fechas que exigen contacto.
    Solo lista las de hoy en adelante (las pasadas no sirven para reservar)."""
    hoy = date.today()
    proximas = {f: m for f, m in fechas().items() if f >= hoy}
    if not proximas:
        return ''
    lineas = [f'- {f.isoformat()} ({f.strftime("%d/%m")}){f" — {m}" if m else ""}'
              for f, m in sorted(proximas.items())]
    return ('FECHAS CON CONTACTO OBLIGATORIO (reservas de esos días):\n'
            + '\n'.join(lineas)
            + f'\nPara una reserva en una de esas fechas pedile SÍ O SÍ {ETIQUETA_DATO} '
              'antes de registrarla y pasalo en el campo "contacto" de crear_reserva.')


def _a_fecha(texto: str) -> date | None:
    try:
        return datetime.strptime(texto.strip(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


def _a_dia(cuando: datetime | date | None) -> date | None:
    if isinstance(cuando, datetime):
        return cuando.date()
    return cuando if isinstance(cuando, date) else None
