"""Solicitudes de eventos (corporativos / privados / sociales).

El bot arma la solicitud conversando; acá se guarda en la DB y se manda un
resumen a cada destinatario configurado, por WhatsApp y por email.
"""
from __future__ import annotations

import notificaciones
from database import SessionLocal
from models import DestinatarioEvento, SolicitudEvento

_CAMPOS = ('tipo_evento', 'nombre_contacto', 'empresa', 'email_contacto',
           'telefono_contacto', 'horario_contacto', 'fecha_estimada',
           'cantidad_personas', 'detalle')


def crear_solicitud(wa_id: str, datos: dict) -> dict:
    db = SessionLocal()
    try:
        solicitud = SolicitudEvento(wa_id=wa_id, **{c: datos.get(c) for c in _CAMPOS})
        db.add(solicitud)
        db.commit()
        sid = solicitud.id
        resumen = _resumen(solicitud)
    except Exception as e:
        db.rollback()
        print(f"[Eventos] Error creando solicitud: {e}")
        return {'ok': False, 'mensaje': 'No pude registrar la solicitud, probá de nuevo.'}
    finally:
        db.close()

    enviados = _notificar_destinatarios(resumen)
    return {'ok': True, 'solicitud_id': sid, 'notificados': enviados,
            'mensaje': 'Solicitud registrada. El equipo de eventos se va a contactar a la brevedad.'}


def _notificar_destinatarios(resumen: str) -> int:
    db = SessionLocal()
    try:
        destinatarios = [(d.nombre, d.whatsapp, d.email)
                         for d in db.query(DestinatarioEvento).filter(DestinatarioEvento.activo.is_(True)).all()]
    finally:
        db.close()

    from whatsapp.providers import get_provider
    provider = get_provider()
    asunto = 'Nueva solicitud de evento — SELQUET'
    contador = 0
    for _nombre, whatsapp, email in destinatarios:
        if whatsapp:
            provider.send_message(whatsapp, resumen)
            contador += 1
        if email:
            notificaciones.enviar_email(email, asunto, resumen)
            contador += 1
    return contador


def _resumen(s: SolicitudEvento) -> str:
    lineas = [
        '📅 *Nueva solicitud de evento — SELQUET*',
        f'Tipo: {s.tipo_evento or "—"}',
        f'Contacto: {s.nombre_contacto or "—"}' + (f' ({s.empresa})' if s.empresa else ''),
        f'Fecha estimada: {s.fecha_estimada or "—"}',
        f'Personas: {s.cantidad_personas if s.cantidad_personas is not None else "—"}',
    ]
    if s.telefono_contacto:
        lineas.append(f'Teléfono: {s.telefono_contacto}')
    if s.email_contacto:
        lineas.append(f'Email: {s.email_contacto}')
    if s.horario_contacto:
        lineas.append(f'Contactar en: {s.horario_contacto}')
    if s.detalle:
        lineas.append(f'Detalle: {s.detalle}')
    lineas.append(f'WhatsApp de origen: {s.wa_id}')
    return '\n'.join(lineas)
