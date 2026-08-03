"""Solicitudes de eventos (corporativos / privados / sociales).

El bot arma la solicitud conversando; acá se guarda en la DB y se manda un
resumen a cada destinatario configurado, por WhatsApp y por email.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import notificaciones
from database import SessionLocal
from models import BorradorEvento, DestinatarioEvento, SolicitudEvento

_CAMPOS = ('tipo_evento', 'nombre_contacto', 'empresa', 'email_contacto',
           'telefono_contacto', 'horario_contacto', 'fecha_estimada',
           'cantidad_personas', 'detalle')

# Mínimos para poder registrar cualquier evento.
_REQUERIDOS = ('tipo_evento', 'nombre_contacto', 'fecha_estimada', 'cantidad_personas')

# Etiquetas legibles para el resumen que se inyecta en el prompt.
_LABELS = {
    'tipo_evento': 'Tipo', 'nombre_contacto': 'Contacto', 'empresa': 'Empresa',
    'email_contacto': 'Email', 'telefono_contacto': 'Teléfono',
    'horario_contacto': 'Horario para contactarlo', 'fecha_estimada': 'Fecha estimada',
    'cantidad_personas': 'Personas', 'detalle': 'Requerimientos',
}


def _vacio(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _es_corporativo(tipo) -> bool:
    return 'corp' in (tipo or '').lower()


def _faltantes(datos: dict) -> list[str]:
    """Campos requeridos que todavía no están. En corporativos se exige además un
    dato de contacto (teléfono o email) y el horario para llamarlo."""
    faltan = [_LABELS[c] for c in _REQUERIDOS if _vacio(datos.get(c))]
    if _es_corporativo(datos.get('tipo_evento')):
        if _vacio(datos.get('telefono_contacto')) and _vacio(datos.get('email_contacto')):
            faltan.append('un contacto (teléfono o email)')
        if _vacio(datos.get('horario_contacto')):
            faltan.append(_LABELS['horario_contacto'])
    return faltan


def _solo_presentes(datos: dict) -> dict:
    return {c: datos[c] for c in _CAMPOS if not _vacio(datos.get(c))}


def guardar_borrador(wa_id: str, datos: dict) -> dict:
    """Mergea en el borrador del teléfono los datos no vacíos que lleguen y
    devuelve el estado (qué se tiene, qué falta). Un borrador abierto por wa_id."""
    nuevos = _solo_presentes(datos)
    db = SessionLocal()
    try:
        b = db.query(BorradorEvento).filter_by(wa_id=wa_id).one_or_none()
        if b is None:
            b = BorradorEvento(wa_id=wa_id)
            db.add(b)
        for k, v in nuevos.items():
            setattr(b, k, v)
        db.commit()
        actual = {c: getattr(b, c) for c in _CAMPOS}
    except Exception as e:
        db.rollback()
        print(f"[Eventos] Error guardando borrador: {e}")
        return {'ok': False, 'mensaje': 'No pude guardar ese dato, seguí igual.'}
    finally:
        db.close()

    faltan = _faltantes(actual)
    return {'ok': True, 'guardado': _solo_presentes(actual), 'faltan': faltan,
            'listo_para_registrar': not faltan}


def estado_borrador_texto(wa_id: str) -> str | None:
    """Bloque para inyectar en el prompt con lo ya capturado del evento en curso,
    o None si no hay borrador. Le da al bot memoria del formulario independiente
    de la ventana del historial."""
    db = SessionLocal()
    try:
        b = db.query(BorradorEvento).filter_by(wa_id=wa_id).one_or_none()
        actual = {c: getattr(b, c) for c in _CAMPOS} if b else None
    finally:
        db.close()
    if not actual:
        return None
    presentes = _solo_presentes(actual)
    if not presentes:
        return None
    lineas = [f'- {_LABELS[c]}: {presentes[c]}' for c in _CAMPOS if c in presentes]
    faltan = _faltantes(actual)
    texto = ('EVENTO EN CURSO — datos ya tomados (NO los vuelvas a pedir):\n'
             + '\n'.join(lineas))
    if faltan:
        texto += '\nTe falta pedir: ' + ', '.join(faltan) + '.'
    else:
        texto += '\nYa tenés todo: confirmá el resumen y registralo con crear_solicitud_evento.'
    return texto


def borrador_completo(wa_id: str) -> bool:
    """True si hay un borrador con todos los datos requeridos (listo para registrar)."""
    db = SessionLocal()
    try:
        b = db.query(BorradorEvento).filter_by(wa_id=wa_id).one_or_none()
        actual = {c: getattr(b, c) for c in _CAMPOS} if b else None
    finally:
        db.close()
    return bool(actual) and not _faltantes(actual)


def descartar_borrador(wa_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(BorradorEvento).filter_by(wa_id=wa_id).delete(synchronize_session=False)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Eventos] Error descartando borrador: {e}")
    finally:
        db.close()


def crear_solicitud(wa_id: str, datos: dict) -> dict:
    db = SessionLocal()
    try:
        b = db.query(BorradorEvento).filter_by(wa_id=wa_id).one_or_none()
        base = {c: getattr(b, c) for c in _CAMPOS} if b else {}
        # Lo que llega en la tool pisa al borrador; el borrador cubre lo que se
        # haya caído del historial.
        merged = {**base, **_solo_presentes(datos)}
        # Anti-duplicado: si el modelo llama dos veces, no crea dos solicitudes iguales.
        reciente = db.query(SolicitudEvento).filter(
            SolicitudEvento.wa_id == wa_id,
            SolicitudEvento.tipo_evento == merged.get('tipo_evento'),
            SolicitudEvento.fecha_estimada == merged.get('fecha_estimada'),
            SolicitudEvento.cantidad_personas == merged.get('cantidad_personas'),
            SolicitudEvento.creado_en >= datetime.now() - timedelta(minutes=3),
        ).first()
        if reciente:
            if b is not None:
                db.delete(b)
                db.commit()
            return {'ok': True, 'solicitud_id': reciente.id, 'duplicado': True,
                    'mensaje': 'Esa solicitud ya quedó registrada.'}
        solicitud = SolicitudEvento(wa_id=wa_id, **{c: merged.get(c) for c in _CAMPOS})
        db.add(solicitud)
        if b is not None:
            db.delete(b)
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
