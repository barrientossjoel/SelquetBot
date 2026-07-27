"""Arma el bloque "datos del local" que se inyecta en el prompt del bot,
leído siempre de la DB (base de conocimiento + menú + FAQs). Así el bot no
tiene datos propios: refleja lo que el panel tenga cargado en ese momento.
"""
from __future__ import annotations

from config_store import CAMPOS_INFO, CLAVES_ESPECIALES, get_all_config
from database import SessionLocal
from formato import pesos
from models import Faq, MenuItem


def build_datos_local() -> str:
    partes = [_bloque_info(), _bloque_menu(), _bloque_faqs()]
    return "\n\n".join(p for p in partes if p)


def _bloque_info() -> str:
    cfg = get_all_config()
    lineas = [
        f"- {campo['label_bot']}: {cfg[campo['clave']].strip()}"
        for campo in CAMPOS_INFO
        if campo['clave'] not in CLAVES_ESPECIALES and cfg.get(campo['clave'], '').strip()
    ]
    return "DATOS DEL LOCAL:\n" + "\n".join(lineas) if lineas else ""


def _bloque_menu() -> str:
    db = SessionLocal()
    try:
        items = db.query(MenuItem).order_by(MenuItem.categoria, MenuItem.nombre).all()
    finally:
        db.close()
    if not items:
        return ""
    lineas = []
    for item in items:
        estado = "" if item.disponible else "  (HOY NO HAY)"
        lineas.append(f"- {item.nombre} [{item.categoria}]: {pesos(item.precio)}{estado}")
    return "MENÚ (usá estos precios y disponibilidad, no inventes):\n" + "\n".join(lineas)


def _bloque_faqs() -> str:
    db = SessionLocal()
    try:
        faqs = db.query(Faq).filter(Faq.activo.is_(True)).order_by(Faq.id).all()
    finally:
        db.close()
    if not faqs:
        return ""
    lineas = [f"- {f.pregunta.strip()} → {f.respuesta.strip()}" for f in faqs]
    return "OTRAS RESPUESTAS:\n" + "\n".join(lineas)
