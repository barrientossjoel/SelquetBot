"""Fechas especiales de reservas: días en los que el local cambia la regla.

Dos listados, los dos editables desde el panel (tabla `config`, clave-valor):
- `CONTACTO_OBLIGATORIO`: ese día la reserva exige un dato de contacto.
- `SIN_DISPONIBILIDAD`: ese día ya está todo reservado y no se toman más reservas.

Formato del valor guardado: una fecha por línea, `YYYY-MM-DD`, con un motivo
opcional después de `|` (ej. `2026-10-18 | Día de la Madre`).
"""
from __future__ import annotations

import re
from datetime import date, datetime

from config_store import get_config, set_config

ETIQUETA_DATO = 'un dato de contacto (teléfono o email)'
_MIN_DIGITOS_TEL = 8
_RE_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$')


class ListadoFechas:
    """Listado de fechas (con su motivo) guardado en una clave de config.

    Una instancia por regla: el resto del sistema pregunta `contiene(fecha)` y
    el panel edita el texto crudo con `texto_config()` / `guardar()`.
    """

    def __init__(self, clave: str, default: str = '', titulo_prompt: str = '',
                 instruccion_prompt: str = ''):
        self.clave = clave
        self.default = default
        self.titulo_prompt = titulo_prompt
        self.instruccion_prompt = instruccion_prompt

    def fechas(self) -> dict[date, str]:
        """`{fecha: motivo}` según la config. Las líneas inválidas se ignoran."""
        resultado: dict[date, str] = {}
        for linea in get_config(self.clave, self.default).splitlines():
            fecha, motivo = _parsear(linea)
            if fecha:
                resultado[fecha] = motivo
        return resultado

    def contiene(self, cuando: datetime | date | None) -> bool:
        return _a_dia(cuando) in self.fechas()

    def motivo(self, cuando: datetime | date | None) -> str:
        """Motivo configurado para ese día ('Día de la Madre'), o '' si no hay."""
        return self.fechas().get(_a_dia(cuando), '')

    def texto_config(self) -> str:
        """Valor crudo, para el textarea del panel."""
        return get_config(self.clave, self.default)

    def guardar(self, texto: str) -> tuple[int, list[str]]:
        """Normaliza y guarda el listado. Si alguna línea no se entiende NO guarda
        nada (para no borrar sin querer las fechas ya cargadas).
        Devuelve (fechas guardadas, líneas inválidas)."""
        validas: list[str] = []
        invalidas: list[str] = []
        for linea in (texto or '').splitlines():
            if not linea.strip():
                continue
            fecha, motivo = _parsear(linea)
            if not fecha:
                invalidas.append(linea.strip())
                continue
            validas.append(f'{fecha.isoformat()} | {motivo}' if motivo else fecha.isoformat())
        if invalidas:
            return 0, invalidas
        set_config({self.clave: '\n'.join(validas)})
        return len(validas), []

    def bloque_prompt(self, excluir: set[date] | None = None) -> str:
        """Bloque para el prompt del bot. Solo lista las fechas de hoy en adelante
        (las pasadas no sirven para reservar), salteando las de `excluir`."""
        hoy = date.today()
        omitir = excluir or set()
        proximas = {f: m for f, m in self.fechas().items() if f >= hoy and f not in omitir}
        if not proximas:
            return ''
        lineas = [f'- {f.isoformat()} ({_dia_humano(f)}){f" — {m}" if m else ""}'
                  for f, m in sorted(proximas.items())]
        return f'{self.titulo_prompt}:\n' + '\n'.join(lineas) + f'\n{self.instruccion_prompt}'


CONTACTO_OBLIGATORIO = ListadoFechas(
    'fechas_contacto_obligatorio',
    default='2026-10-18 | Día de la Madre',
    titulo_prompt='FECHAS CON CONTACTO OBLIGATORIO (reservas de esos días)',
    instruccion_prompt=f'Para una reserva en una de esas fechas pedile SÍ O SÍ {ETIQUETA_DATO} '
                       'antes de registrarla y pasalo en el campo "contacto" de crear_reserva.',
)

SIN_DISPONIBILIDAD = ListadoFechas(
    'fechas_sin_disponibilidad',
    default='2026-10-18 | Día de la Madre',
    titulo_prompt='FECHAS SIN DISPONIBILIDAD — YA ESTÁ TODO RESERVADO (no tomes reservas)',
    instruccion_prompt='Si alguien quiere reservar para una de esas fechas, decile con amabilidad '
                       'que ese día ya está TODO RESERVADO y que no quedan mesas. No lo anotes en '
                       'lista de espera ni prometas avisarle si se libera algo: ofrecele otra fecha '
                       'u otro horario, o pedir para llevar. Si es un evento o un grupo grande para '
                       'esa fecha, tomale los datos igual para que el equipo lo contacte.',
)

# Listados que el panel permite editar (clave de la URL → listado).
EDITABLES = {'contacto': CONTACTO_OBLIGATORIO, 'sin-lugar': SIN_DISPONIBILIDAD}


def bloques_prompt() -> list[str]:
    """Bloques de fechas especiales para inyectar en el prompt (los que tengan algo).

    Una fecha cerrada no aparece en el bloque de contacto obligatorio: ahí no se
    toman reservas, así que pedir el contacto sería una instrucción contradictoria.
    """
    cerradas = set(SIN_DISPONIBILIDAD.fechas())
    bloques = (SIN_DISPONIBILIDAD.bloque_prompt(),
               CONTACTO_OBLIGATORIO.bloque_prompt(excluir=cerradas))
    return [b for b in bloques if b]


def contacto_valido(contacto: str | None) -> bool:
    """Acepta un email, o un teléfono con al menos 8 dígitos."""
    texto = (contacto or '').strip()
    if not texto:
        return False
    if '@' in texto:
        return bool(_RE_EMAIL.match(texto))
    return sum(c.isdigit() for c in texto) >= _MIN_DIGITOS_TEL


def _parsear(linea: str) -> tuple[date | None, str]:
    fecha_txt, _, motivo_txt = (linea or '').partition('|')
    return _a_fecha(fecha_txt), motivo_txt.strip()


def _a_fecha(texto: str) -> date | None:
    try:
        return datetime.strptime(texto.strip(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


def _a_dia(cuando: datetime | date | None) -> date | None:
    if isinstance(cuando, datetime):
        return cuando.date()
    return cuando if isinstance(cuando, date) else None


_DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')


def _dia_humano(f: date) -> str:
    return f'{_DIAS[f.weekday()]} {f.day:02d}/{f.month:02d}'
