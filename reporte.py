"""Reporte diario de eventos al jefe (por WhatsApp y email).

Arma un resumen de las solicitudes de eventos del día y cuántas fueron
contactadas, y lo manda al contacto configurado como "jefe".
"""
from __future__ import annotations

from datetime import datetime, timedelta

import config_store
import notificaciones
from database import SessionLocal
from models import SolicitudEvento


def generar(fecha=None) -> str:
    dia = (fecha or datetime.now()).date()
    inicio = datetime(dia.year, dia.month, dia.day)
    fin = inicio + timedelta(days=1)
    db = SessionLocal()
    try:
        solicitudes = db.query(SolicitudEvento).filter(
            SolicitudEvento.creado_en >= inicio,
            SolicitudEvento.creado_en < fin,
        ).order_by(SolicitudEvento.creado_en).all()
        filas = [(s.tipo_evento, s.nombre_contacto or s.wa_id, s.empresa, s.cantidad_personas, s.estado)
                 for s in solicitudes]
    finally:
        db.close()

    total = len(filas)
    contactadas = sum(1 for f in filas if f[4] in ('contactado', 'confirmada'))
    lineas = [
        f'📊 *Reporte del día {dia.strftime("%d/%m")} — SELQUET*',
        f'Solicitudes de eventos: {total}',
        f'Contactadas: {contactadas} de {total}',
    ]
    if filas:
        lineas.append('')
        for tipo, nombre, empresa, personas, estado in filas:
            emp = f' ({empresa})' if empresa else ''
            per = f' · {personas} pers' if personas else ''
            lineas.append(f'• {tipo or "evento"}: {nombre}{emp}{per} — {estado}')
    else:
        lineas.append('Sin solicitudes hoy.')
    return '\n'.join(lineas)


def enviar(fecha=None) -> dict:
    texto = generar(fecha)
    whatsapps = _lista(config_store.get_config('jefe_whatsapp', ''))
    emails = _lista(config_store.get_config('jefe_email', ''))
    enviados = 0
    if whatsapps:
        from whatsapp.providers import get_provider
        provider = get_provider()
        for numero in whatsapps:
            provider.send_message(numero, texto)
            enviados += 1
    for email in emails:
        notificaciones.enviar_email(email, 'Reporte diario de eventos — SELQUET', texto)
        enviados += 1
    if not (whatsapps or emails):
        print('[Reporte] No hay jefes configurados (jefe_whatsapp / jefe_email).')
    return {'enviados': enviados, 'texto': texto}


def _lista(valor: str) -> list[str]:
    import re
    return [x.strip() for x in re.split(r'[,\n;]+', valor or '') if x.strip()]
