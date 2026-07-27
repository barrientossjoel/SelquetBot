"""Acceso a la configuración del local (tabla `config`, clave-valor).

Compartido entre el panel admin (que lo edita) y el chat_engine (que lo lee).
`CAMPOS_INFO` define los campos fijos de la solapa "Información": el mismo
listado se usa para renderizar el formulario y para armar el contexto del bot.
"""
from __future__ import annotations

from database import SessionLocal
from models import Config

# Campos fijos de la base de conocimiento. `label_bot` es cómo se nombra el dato
# dentro del prompt del bot.
CAMPOS_INFO = [
    {'clave': 'nombre_local',       'label': 'Nombre del local',            'tipo': 'text',     'label_bot': 'Nombre'},
    {'clave': 'horarios',           'label': 'Horarios de atención',        'tipo': 'textarea', 'label_bot': 'Horarios'},
    {'clave': 'direccion',          'label': 'Dirección',                   'tipo': 'text',     'label_bot': 'Dirección'},
    {'clave': 'como_llegar',        'label': 'Cómo llegar',                 'tipo': 'text',     'label_bot': 'Cómo llegar'},
    {'clave': 'estacionamiento',    'label': 'Estacionamiento',             'tipo': 'text',     'label_bot': 'Estacionamiento'},
    {'clave': 'formas_pago',        'label': 'Formas de pago',              'tipo': 'text',     'label_bot': 'Formas de pago'},
    {'clave': 'descuentos',         'label': 'Descuentos',                  'tipo': 'text',     'label_bot': 'Descuentos'},
    {'clave': 'pedido_minimo',      'label': 'Pedido mínimo (para llevar)', 'tipo': 'text',     'label_bot': 'Pedido mínimo'},
    {'clave': 'tiempo_preparacion', 'label': 'Tiempo de preparación (min)', 'tipo': 'text',     'label_bot': 'Tiempo de preparación (min)'},
    {'clave': 'wifi',               'label': 'WiFi',                        'tipo': 'text',     'label_bot': 'WiFi'},
    {'clave': 'accesibilidad',      'label': 'Accesibilidad',               'tipo': 'text',     'label_bot': 'Accesibilidad'},
    {'clave': 'extra',              'label': 'Notas extra',                 'tipo': 'textarea', 'label_bot': 'Otros'},
    {'clave': 'mensaje_bienvenida', 'label': 'Mensaje de bienvenida (saludo inicial / al arrancar un pedido)', 'tipo': 'textarea', 'label_bot': '—'},
]

# Claves de config que NO van al bloque de datos del bot (se usan aparte).
CLAVES_ESPECIALES = ('nombre_local', 'mensaje_bienvenida')

CLAVE_BOT_ACTIVO = 'bot_activo'


def get_all_config() -> dict[str, str]:
    db = SessionLocal()
    try:
        return {row.clave: row.valor for row in db.query(Config).all()}
    finally:
        db.close()


def get_config(clave: str, default: str = '') -> str:
    return get_all_config().get(clave, default)


def set_config(valores: dict[str, str]) -> None:
    """Upsert de una o varias claves (único punto de escritura)."""
    db = SessionLocal()
    try:
        for clave, valor in valores.items():
            row = db.get(Config, clave)
            if row is None:
                db.add(Config(clave=clave, valor=valor or ''))
            else:
                row.valor = valor or ''
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Config] Error guardando {list(valores)}: {e}")
    finally:
        db.close()


def is_bot_activo() -> bool:
    return get_config(CLAVE_BOT_ACTIVO, '1') == '1'


def set_bot_activo(activo: bool) -> None:
    set_config({CLAVE_BOT_ACTIVO: '1' if activo else '0'})
