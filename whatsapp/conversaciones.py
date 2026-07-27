"""Historial conversacional del bot de SELQUET.

Scope por `telefono` (clientes anónimos, sin login).
Ventana: últimos N turnos o últimos M minutos, lo que sea más restrictivo.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from database import SessionLocal
from models import WhatsAppConversacion

MAX_TURNOS = 12          # ~6 turnos usuario + 6 asistente
VENTANA_MINUTOS = 30     # una consulta de hace horas no contamina el contexto
TTL_HORAS = 24           # cleanup


def cargar_historial(telefono: str) -> list[dict]:
    """Devuelve los mensajes recientes en formato Anthropic ([{role, content}, ...])."""
    db = SessionLocal()
    try:
        corte = datetime.now() - timedelta(minutes=VENTANA_MINUTOS)
        registros = db.query(WhatsAppConversacion).filter(
            WhatsAppConversacion.telefono == telefono,
            WhatsAppConversacion.created_at >= corte,
        ).order_by(WhatsAppConversacion.created_at.desc()).limit(MAX_TURNOS).all()
        registros.reverse()
        return [{'role': r.role, 'content': r.content} for r in registros]
    finally:
        db.close()


def guardar_turno(telefono: str, role: str, content) -> None:
    """Persiste un turno. `content` debe ser serializable a JSON."""
    db = SessionLocal()
    try:
        db.add(WhatsAppConversacion(telefono=telefono, role=role, content=content))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[SELQUET Conv] Error guardando turno: {e}")
    finally:
        db.close()


def borrar_antiguas() -> int:
    """Elimina conversaciones > TTL_HORAS. Retorna cantidad borrada."""
    db = SessionLocal()
    try:
        corte = datetime.now() - timedelta(hours=TTL_HORAS)
        n = db.query(WhatsAppConversacion).filter(
            WhatsAppConversacion.created_at < corte
        ).delete(synchronize_session=False)
        db.commit()
        return n
    except Exception as e:
        db.rollback()
        print(f"[SELQUET Conv] Error en cleanup: {e}")
        return 0
    finally:
        db.close()


def reset_conversacion(telefono: str) -> int:
    """Borra el historial de un teléfono."""
    db = SessionLocal()
    try:
        n = db.query(WhatsAppConversacion).filter(
            WhatsAppConversacion.telefono == telefono
        ).delete(synchronize_session=False)
        db.commit()
        return n
    except Exception as e:
        db.rollback()
        print(f"[SELQUET Conv] Error reseteando: {e}")
        return 0
    finally:
        db.close()
