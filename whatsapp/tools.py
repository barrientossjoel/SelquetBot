"""Tools (function calling) del bot: acciones sobre la DB.

Las consultas de info y menú NO son tools (se inyectan en el contexto del prompt).
Las tools son solo para ACCIONES: consultar disponibilidad, reservar, opinar.
"""
from __future__ import annotations

from datetime import datetime

import eventos
import pedidos
import reservas
from database import SessionLocal
from models import Opinion

TOOLS = [
    {
        'name': 'consultar_disponibilidad',
        'description': 'Verifica si hay lugar para una reserva en una fecha, hora y cantidad de personas. '
                       'Usalo cuando el cliente pregunta si hay lugar, antes de confirmar la reserva.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'fecha': {'type': 'string', 'description': 'Fecha en formato YYYY-MM-DD.'},
                'hora': {'type': 'string', 'description': 'Hora en formato HH:MM (24h).'},
                'personas': {'type': 'integer', 'description': 'Cantidad de personas.'},
            },
            'required': ['fecha', 'hora', 'personas'],
        },
    },
    {
        'name': 'crear_reserva',
        'description': 'Registra una reserva (re-verifica disponibilidad). Antes de llamarla asegurate de '
                       'tener nombre, fecha, hora y personas. La reserva queda pendiente de que el local la confirme.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'nombre': {'type': 'string', 'description': 'Nombre de quien reserva.'},
                'fecha': {'type': 'string', 'description': 'Fecha en formato YYYY-MM-DD.'},
                'hora': {'type': 'string', 'description': 'Hora en formato HH:MM (24h).'},
                'personas': {'type': 'integer', 'description': 'Cantidad de personas.'},
            },
            'required': ['fecha', 'hora', 'personas'],
        },
    },
    {
        'name': 'crear_pedido',
        'description': 'Arma un pedido para llevar: calcula el total desde el menú, valida el pedido mínimo '
                       'y genera el link de pago de MercadoPago. Antes de llamarla necesitás los productos '
                       'con cantidades y la hora de retiro. Pasale el link al cliente y aclarale que el pedido '
                       'se manda a cocinar recién cuando paga. Usá los nombres tal como figuran en el menú.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'items': {
                    'type': 'array',
                    'description': 'Productos pedidos.',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'nombre': {'type': 'string', 'description': 'Nombre del producto (como en el menú).'},
                            'cantidad': {'type': 'integer'},
                        },
                        'required': ['nombre', 'cantidad'],
                    },
                },
                'hora_retiro': {'type': 'string', 'description': 'Hora de retiro HH:MM (24h).'},
            },
            'required': ['items', 'hora_retiro'],
        },
    },
    {
        'name': 'enviar_carta',
        'description': 'Envía la carta/menú completo en PDF al cliente. Usalo cuando pidan ver la carta, '
                       'el menú completo o la carta en PDF. Para un precio puntual NO uses esto: respondé desde el menú.',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'guardar_dato_evento',
        'description': 'Guarda en un borrador los datos de un evento a medida que el cliente los va dando, '
                       'para no perderlos aunque la charla se alargue. Llamala apenas captures uno o más '
                       'datos (podés mandar solo los que tengas). Devuelve qué datos ya hay y cuáles faltan. '
                       'IMPORTANTE: esta tool NO registra la solicitud ni avisa al equipo, solo guarda datos '
                       'parciales. Para REGISTRAR el evento SIEMPRE tenés que llamar después a crear_solicitud_evento.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'tipo_evento': {'type': 'string', 'description': 'Ej: corporativo, cumpleaños, casamiento, desayuno de negocios…'},
                'nombre_contacto': {'type': 'string', 'description': 'Nombre de quien organiza.'},
                'empresa': {'type': 'string', 'description': 'Empresa, si es corporativo.'},
                'email_contacto': {'type': 'string', 'description': 'Email de contacto.'},
                'telefono_contacto': {'type': 'string', 'description': 'Teléfono de contacto.'},
                'horario_contacto': {'type': 'string', 'description': 'En eventos CORPORATIVOS: franja horaria en que el cliente prefiere que lo contacten.'},
                'fecha_estimada': {'type': 'string', 'description': 'Fecha/horario estimado del evento, como lo diga el cliente.'},
                'cantidad_personas': {'type': 'integer', 'description': 'Cantidad aproximada de asistentes.'},
                'detalle': {'type': 'string', 'description': 'Requerimientos: catering, proyector/AV, disposición de mesas, presupuesto, etc.'},
            },
        },
    },
    {
        'name': 'crear_solicitud_evento',
        'description': 'Registra una solicitud de evento (corporativo, privado o social) y avisa al equipo. '
                       'Llamala cuando ya juntaste los datos del evento (usá antes guardar_dato_evento para '
                       'ir cargándolos). El local se contacta después.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'tipo_evento': {'type': 'string', 'description': 'Ej: corporativo, cumpleaños, casamiento, desayuno de negocios…'},
                'nombre_contacto': {'type': 'string', 'description': 'Nombre de quien organiza.'},
                'empresa': {'type': 'string', 'description': 'Empresa, si es corporativo. Opcional.'},
                'email_contacto': {'type': 'string', 'description': 'Email de contacto.'},
                'telefono_contacto': {'type': 'string', 'description': 'Teléfono de contacto. Opcional.'},
                'horario_contacto': {'type': 'string', 'description': 'En eventos CORPORATIVOS: en qué horario/franja el cliente prefiere que lo contacten para coordinar.'},
                'fecha_estimada': {'type': 'string', 'description': 'Fecha/horario estimado del evento, como lo diga el cliente.'},
                'cantidad_personas': {'type': 'integer', 'description': 'Cantidad aproximada de asistentes.'},
                'detalle': {'type': 'string', 'description': 'Requerimientos: catering, proyector/AV, disposición de mesas, presupuesto, etc.'},
            },
            'required': ['tipo_evento', 'nombre_contacto', 'fecha_estimada', 'cantidad_personas'],
        },
    },
    {
        'name': 'registrar_opinion',
        'description': 'Guarda una opinión, elogio o queja del cliente sobre el local.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'texto': {'type': 'string', 'description': 'La opinión, tal como la dijo el cliente.'},
                'tipo': {'type': 'string', 'enum': ['elogio', 'queja', 'comentario']},
            },
            'required': ['texto'],
        },
    },
]


def ejecutar(nombre: str, params: dict, telefono: str) -> dict:
    try:
        if nombre == 'consultar_disponibilidad':
            return reservas.disponibilidad(_a_fecha_hora(params), int(params['personas']))
        if nombre == 'crear_reserva':
            return reservas.crear(_a_fecha_hora(params), int(params['personas']),
                                  params.get('nombre', ''), telefono)
        if nombre == 'crear_pedido':
            return _crear_pedido(params, telefono)
        if nombre == 'enviar_carta':
            return _enviar_carta(telefono)
        if nombre == 'guardar_dato_evento':
            return eventos.guardar_borrador(telefono, params)
        if nombre == 'crear_solicitud_evento':
            return eventos.crear_solicitud(telefono, params)
        if nombre == 'registrar_opinion':
            return _registrar_opinion(params.get('texto', ''), params.get('tipo', 'comentario'), telefono)
        return {'error': f'Tool desconocida: {nombre}'}
    except (KeyError, ValueError) as e:
        return {'error': f'Parámetros inválidos: {e}'}


def _a_fecha_hora(params: dict) -> datetime:
    return datetime.strptime(f"{params['fecha']} {params['hora']}", '%Y-%m-%d %H:%M')


def _crear_pedido(params: dict, telefono: str) -> dict:
    armado = pedidos.armar_pedido(params.get('items') or [])
    if not armado['ok']:
        return armado
    return pedidos.crear_con_link(telefono, armado['items'], armado['total'],
                                  _hora_retiro(params.get('hora_retiro')))


def _hora_retiro(hhmm) -> datetime | None:
    try:
        h, m = str(hhmm).split(':')
        return datetime.now().replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except (ValueError, AttributeError):
        return None


def _enviar_carta(telefono: str) -> dict:
    import carta
    from .providers import get_provider
    if not carta.existe():
        return {'ok': False, 'mensaje': 'La carta en PDF no está disponible.'}
    link = carta.link_publico()
    if not link:
        return {'ok': False, 'mensaje': 'Falta configurar la URL pública (PUBLIC_BASE_URL o MP_BASE_URL).'}
    ok = get_provider().send_document(telefono, link, filename='Carta SELQUET.pdf')
    return {'ok': ok, 'mensaje': 'Carta enviada por WhatsApp.' if ok else 'No pude enviar la carta.'}


def _registrar_opinion(texto: str, tipo: str, telefono: str) -> dict:
    texto = texto.strip()
    if not texto:
        return {'ok': False, 'mensaje': 'Falta el texto de la opinión.'}
    tipo = tipo if tipo in ('elogio', 'queja', 'comentario') else 'comentario'
    db = SessionLocal()
    try:
        db.add(Opinion(wa_id=telefono, texto=texto, tipo=tipo))
        db.commit()
    except Exception:
        db.rollback()
        return {'ok': False, 'mensaje': 'No pude guardar el comentario.'}
    finally:
        db.close()

    if tipo == 'queja':
        _alertar_queja(telefono, texto)
        return {'ok': True, 'tipo': 'queja',
                'instruccion': ('Mostrá empatía, decile que lamentás lo que pasó y que ya se lo pasás a '
                                'nuestra gerencia de atención al cliente para resolverlo. No prometas nada puntual.')}
    if tipo == 'elogio':
        review = _review_url()
        instr = 'Agradecé con calidez.'
        if review:
            instr += f' Invitalo a dejar su calificación en Google con este link (pasáselo tal cual): {review}'
        return {'ok': True, 'tipo': 'elogio', 'review_url': review, 'instruccion': instr}

    return {'ok': True, 'tipo': 'comentario', 'instruccion': 'Agradecé el comentario.'}


def _review_url() -> str:
    from config_store import get_config
    return get_config('google_review_url', '').strip()


def _alertar_queja(telefono: str, texto: str) -> None:
    """Avisa a los jefes (WhatsApp + email) de una queja, con el contacto del cliente."""
    import re

    import config_store
    import notificaciones

    def _lista(v):
        return [x.strip() for x in re.split(r'[,\n;]+', v or '') if x.strip()]

    nombre_local = config_store.get_config('nombre_local', 'SELQUET')
    msg = (f'⚠️ *Queja de un cliente en {nombre_local}*\n'
           f'Contacto (WhatsApp): {telefono}\n\n"{texto}"\n\n'
           f'Comunicate con el cliente para resolverlo.')
    try:
        from .providers import get_provider
        provider = get_provider()
        for numero in _lista(config_store.get_config('jefe_whatsapp', '')):
            provider.send_message(numero, msg)
    except Exception as e:
        print(f'[Alerta queja] Error WhatsApp: {e}')
    for email in _lista(config_store.get_config('jefe_email', '')):
        notificaciones.enviar_email(email, f'Queja de un cliente — {nombre_local}', msg)
