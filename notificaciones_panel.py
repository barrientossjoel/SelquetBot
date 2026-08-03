"""Notificaciones del panel (mismo patrón que ocr_web).

Cada novedad (pedido, reserva, evento) crea una fila. El navegador las consume
por polling (campana + toast) y quedan marcadas como `notificado` para no
repetirlas. `crear()` se llama desde el dominio al dar de alta cada cosa.
"""
from __future__ import annotations

from database import SessionLocal
from models import NotificacionPanel


def crear(tipo: str, mensaje: str, ref_id: int | None = None) -> None:
    """Registra una notificación para el panel. No rompe el flujo si falla."""
    db = SessionLocal()
    try:
        db.add(NotificacionPanel(tipo=tipo, mensaje=mensaje, ref_id=ref_id))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f'[Notif panel] No se pudo crear: {e}')
    finally:
        db.close()


def pendientes() -> list[dict]:
    """Notificaciones no entregadas todavía; las marca como notificadas."""
    db = SessionLocal()
    try:
        filas = (db.query(NotificacionPanel)
                 .filter(NotificacionPanel.notificado.is_(False))
                 .order_by(NotificacionPanel.id).all())
        datos = [{'id': n.id, 'tipo': n.tipo, 'ref_id': n.ref_id, 'mensaje': n.mensaje} for n in filas]
        for n in filas:
            n.notificado = True
        db.commit()
        return datos
    except Exception as e:
        db.rollback()
        print(f'[Notif panel] Error leyendo pendientes: {e}')
        return []
    finally:
        db.close()
