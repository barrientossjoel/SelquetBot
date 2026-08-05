"""Autenticación y autorización del panel.

Usuarios en la tabla `usuarios`, con rol:
- admin: ve todas las solapas y puede prender/apagar el bot.
- local: solo Eventos y Operación; no puede apagar el bot.

El control de acceso es centralizado (un `before_request` en routes.py lo aplica
a todo el blueprint): acá viven las reglas declarativas y la función que decide.
`SOLAPAS_POR_ROL` es la única fuente de verdad, usada por el backend y por la UI.
"""
from flask import session
from werkzeug.security import check_password_hash

from database import SessionLocal
from models import Usuario

# Solapas accesibles por rol. Mantener alineado con las tabs de base.html.
SOLAPAS_POR_ROL = {
    'admin': ('informacion', 'faqs', 'menu', 'mesas', 'eventos', 'operacion'),
    'local': ('eventos', 'operacion'),
}

# Endpoints del panel que no requieren sesión.
ENDPOINTS_PUBLICOS = ('login', 'logout', 'static')

# Endpoints que requieren sesión pero no pertenecen a una solapa (no se chequea rol).
ENDPOINTS_NEUTROS = ('home',)

# A qué solapa pertenece cada endpoint. Lo que NO figure acá se considera
# configuración → solo admin (fail-closed: una ruta nueva queda protegida por
# defecto hasta clasificarla).
ENDPOINTS_POR_SOLAPA = {
    'eventos': ('eventos', 'eventos_jefe', 'eventos_reporte_enviar',
                'evento_destinatario_nuevo', 'evento_destinatario_toggle',
                'evento_destinatario_borrar', 'solicitud_estado'),
    'operacion': ('operacion', 'operacion_tabla', 'pedidos_config',
                  'notificaciones_pendientes', 'reserva_estado', 'pedido_estado'),
}


def autenticar(username: str, password: str) -> Usuario | None:
    """Devuelve el usuario si las credenciales son válidas y está activo; si no, None."""
    if not (username and password):
        return None
    db = SessionLocal()
    try:
        u = db.query(Usuario).filter(
            Usuario.username == username.strip(),
            Usuario.activo.is_(True),
        ).one_or_none()
        if u and check_password_hash(u.password_hash, password):
            return u
        return None
    finally:
        db.close()


def rol_actual() -> str:
    return session.get('rol', '')


def es_admin() -> bool:
    return rol_actual() == 'admin'


def solapas_permitidas() -> tuple:
    return SOLAPAS_POR_ROL.get(rol_actual(), ())


def landing_endpoint() -> str:
    """Primera solapa según el rol (admin → Información, local → Eventos)."""
    permitidas = solapas_permitidas()
    return f"admin.{permitidas[0]}" if permitidas else 'admin.login'


def _solapa_de_endpoint(nombre: str) -> str | None:
    for solapa, endpoints in ENDPOINTS_POR_SOLAPA.items():
        if nombre in endpoints:
            return solapa
    return None   # no clasificado → configuración (solo admin)


def puede_acceder(rol: str, nombre_endpoint: str) -> bool:
    """Si el rol puede tocar ese endpoint. Admin todo; el resto, solo endpoints
    de una solapa que tenga permitida."""
    if rol == 'admin':
        return True
    solapa = _solapa_de_endpoint(nombre_endpoint)
    return solapa is not None and solapa in SOLAPAS_POR_ROL.get(rol, ())
