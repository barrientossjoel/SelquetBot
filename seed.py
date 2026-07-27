"""Carga inicial de datos. Idempotente: solo escribe si las tablas están vacías,
así el bot arranca con los datos que antes estaban hardcodeados, pero editables
desde el panel. No pisa nada si el local ya cargó lo suyo.
"""
from config_store import set_config
from database import SessionLocal
from models import Config, MenuItem, MesaConfig

_CONFIG_INICIAL = {
    'nombre_local': 'SELQUET',
    'horarios': 'Martes a domingo, de 12:00 a 15:30 y de 20:00 a 00:00. Lunes cerrado.',
    'direccion': 'Av. Corrientes 1234, CABA.',
    'como_llegar': 'A una cuadra del subte B.',
    'estacionamiento': 'Sí, playa de estacionamiento propia sin cargo para clientes.',
    'formas_pago': 'Efectivo, débito, crédito (Visa/Mastercard) y Mercado Pago.',
    'descuentos': '',
    'pedido_minimo': '',
    'tiempo_preparacion': '30',
    'wifi': 'Sí, gratis. Se pide la clave al mozo.',
    'accesibilidad': 'Local en planta baja, apto para sillas de ruedas.',
    'extra': '',
    'bot_activo': '1',
}

_MENU_INICIAL = [
    ('Milanesa napolitana con papas fritas', 'Platos',   8500),
    ('Bife de chorizo con guarnición',       'Platos',  12000),
    ('Provoleta',                            'Entradas', 4200),
    ('Empanadas (unidad)',                   'Entradas', 1100),
    ('Ensalada César',                       'Platos',   6800),
    ('Ravioles de ricota con salsa',         'Platos',   7900),
    ('Flan casero con dulce de leche',       'Postres',  3500),
    ('Agua / gaseosa línea Coca',            'Bebidas',  1800),
]

# Martes(1) a domingo(6), almuerzo y cena. Lunes(0) cerrado. 12 mesas de 4, 90 min.
_MESAS_INICIAL = [
    (dia, desde, hasta)
    for dia in range(1, 7)
    for desde, hasta in (('12:00', '15:30'), ('20:00', '23:59'))
]


def seed():
    db = SessionLocal()
    try:
        config_vacia = db.query(Config).count() == 0
        menu_vacio = db.query(MenuItem).count() == 0
    finally:
        db.close()

    if config_vacia:
        set_config(_CONFIG_INICIAL)

    if menu_vacio:
        db = SessionLocal()
        try:
            db.add_all([
                MenuItem(nombre=n, categoria=c, precio=p, disponible=True)
                for n, c, p in _MENU_INICIAL
            ])
            db.commit()
        finally:
            db.close()

    db = SessionLocal()
    try:
        mesas_vacias = db.query(MesaConfig).count() == 0
    finally:
        db.close()

    if mesas_vacias:
        db = SessionLocal()
        try:
            db.add_all([
                MesaConfig(dia_semana=dia, hora_desde=desde, hora_hasta=hasta,
                           cantidad_mesas=12, capacidad=4, duracion_min=90)
                for dia, desde, hasta in _MESAS_INICIAL
            ])
            db.commit()
        finally:
            db.close()
