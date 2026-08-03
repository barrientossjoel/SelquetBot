"""Disponibilidad y alta de reservas (opción completa).

Modelo: por día de semana + franja horaria, el local define cantidad de mesas,
capacidad por mesa y duración de la reserva. Disponibilidad = mesas de la franja
menos las reservas activas que se solapan con el horario pedido.
Supuestos: 1 reserva = 1 mesa; grupos > capacidad se derivan a llamar al local.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from database import SessionLocal
from models import MesaConfig, Reserva

DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
_ESTADOS_ACTIVOS = ('nueva', 'confirmada')


def disponibilidad(fecha_hora: datetime, personas: int) -> dict:
    config = _config_para(fecha_hora)
    if config is None:
        return {'disponible': False, 'motivo': 'sin_horario',
                'mensaje': 'No tomamos reservas para ese día u horario.'}
    if personas > config.capacidad:
        return {'disponible': False, 'motivo': 'grupo_grande',
                'mensaje': f'Para grupos de más de {config.capacidad} personas se maneja como evento: '
                           f'tomale los datos y registralo con crear_solicitud_evento (no le digas que llame al local).'}
    libres = config.cantidad_mesas - _reservas_solapadas(fecha_hora, config.duracion_min)
    if libres > 0:
        return {'disponible': True, 'mesas_libres': libres,
                'mensaje': f'Hay lugar para ese horario ({libres} mesa/s libre/s).'}
    return {'disponible': False, 'motivo': 'completo',
            'mensaje': 'No hay mesas libres para ese horario. ¿Probamos con otro?'}


def crear(fecha_hora: datetime, personas: int, nombre: str, wa_id: str) -> dict:
    disp = disponibilidad(fecha_hora, personas)
    if not disp['disponible']:
        return {'ok': False, **disp}
    db = SessionLocal()
    try:
        # Anti-duplicado: si el modelo llama dos veces, no crea dos reservas iguales.
        reciente = db.query(Reserva).filter(
            Reserva.wa_id == wa_id, Reserva.fecha_hora == fecha_hora,
            Reserva.personas == personas,
            Reserva.creado_en >= datetime.now() - timedelta(minutes=3),
        ).first()
        if reciente:
            return {'ok': True, 'reserva_id': reciente.id, 'duplicado': True,
                    'mensaje': 'Esa reserva ya quedó registrada.'}
        reserva = Reserva(wa_id=wa_id, nombre=(nombre or '').strip() or None,
                          fecha_hora=fecha_hora, personas=personas, estado='nueva')
        db.add(reserva)
        db.commit()
        return {'ok': True, 'reserva_id': reserva.id,
                'mensaje': f'Reserva registrada para {personas} persona/s el '
                           f'{fecha_hora.strftime("%d/%m a las %H:%M")}. '
                           f'Queda pendiente de que el local la confirme.'}
    except Exception as e:
        db.rollback()
        print(f"[Reservas] Error creando: {e}")
        return {'ok': False, 'mensaje': 'No pude registrar la reserva, probá de nuevo.'}
    finally:
        db.close()


def _config_para(fecha_hora: datetime):
    db = SessionLocal()
    try:
        filas = db.query(MesaConfig).filter(MesaConfig.dia_semana == fecha_hora.weekday()).all()
    finally:
        db.close()
    req = fecha_hora.hour * 60 + fecha_hora.minute
    for c in filas:
        if _en_franja(req, _a_min(c.hora_desde), _a_min(c.hora_hasta)):
            return c
    return None


def _reservas_solapadas(fecha_hora: datetime, dur_min: int) -> int:
    inicio, fin = fecha_hora, fecha_hora + timedelta(minutes=dur_min)
    db = SessionLocal()
    try:
        candidatas = db.query(Reserva).filter(
            Reserva.estado.in_(_ESTADOS_ACTIVOS),
            Reserva.fecha_hora >= inicio - timedelta(minutes=dur_min),
            Reserva.fecha_hora < fin,
        ).all()
    finally:
        db.close()
    return sum(1 for r in candidatas
               if r.fecha_hora < fin and inicio < r.fecha_hora + timedelta(minutes=dur_min))


def _a_min(hhmm: str) -> int:
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


def _en_franja(req: int, desde: int, hasta: int) -> bool:
    if hasta == 0:
        hasta = 1440  # '00:00' = fin del día
    if hasta > desde:
        return desde <= req < hasta
    return req >= desde or req < hasta  # franja que cruza medianoche
