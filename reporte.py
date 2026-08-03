"""Reporte diario a los jefes (por WhatsApp y email).

Resume el día: pedidos (realizados/cobrados/entregados), solicitudes de eventos y
cuántas se contactaron, mesas reservadas, feedback de clientes (con link para ver
los comentarios) y cambios de precio (solo si hubo).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import config_store
import notificaciones
from database import SessionLocal
from models import CambioPrecio, Opinion, Pedido, Reserva, SolicitudEvento


def _pesos(n) -> str:
    try:
        return '$' + f'{int(n):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return f'${n}'


def generar(fecha=None) -> str:
    dia = (fecha or datetime.now()).date()
    inicio = datetime(dia.year, dia.month, dia.day)
    fin = inicio + timedelta(days=1)

    db = SessionLocal()
    try:
        solicitudes = db.query(SolicitudEvento).filter(
            SolicitudEvento.creado_en >= inicio, SolicitudEvento.creado_en < fin,
        ).order_by(SolicitudEvento.creado_en).all()
        eventos = [(s.tipo_evento, s.nombre_contacto or s.wa_id, s.empresa,
                    s.cantidad_personas, s.estado) for s in solicitudes]

        pedidos = db.query(Pedido).filter(
            Pedido.creado_en >= inicio, Pedido.creado_en < fin,
        ).all()
        ped = [(p.metodo_pago, p.estado, p.total) for p in pedidos]

        reservas_hoy = db.query(Reserva).filter(
            Reserva.fecha_hora >= inicio, Reserva.fecha_hora < fin,
            Reserva.estado != 'cancelada',
        ).count()

        opiniones = [o.tipo for o in db.query(Opinion).filter(
            Opinion.creado_en >= inicio, Opinion.creado_en < fin,
        ).all()]

        cambios = [(c.item_nombre, c.precio_anterior, c.precio_nuevo)
                   for c in db.query(CambioPrecio).filter(
                       CambioPrecio.creado_en >= inicio, CambioPrecio.creado_en < fin,
                   ).order_by(CambioPrecio.creado_en).all()]
    finally:
        db.close()

    # Pedidos
    realizados = sum(1 for _m, e, _t in ped if e != 'cancelado')
    cobrados = [(m, e, t) for m, e, t in ped
                if (m == 'mercadopago' and e in ('pagado', 'preparado', 'retirado'))
                or (m != 'mercadopago' and e == 'retirado')]
    entregados = sum(1 for _m, e, _t in ped if e == 'retirado')
    monto_cobrado = sum(t for _m, _e, t in cobrados)

    # Eventos
    total_ev = len(eventos)
    contactadas = sum(1 for f in eventos if f[4] in ('contactado', 'confirmada'))

    # Opiniones
    total_op = len(opiniones)
    buenas = sum(1 for t in opiniones if t == 'elogio')
    malas = sum(1 for t in opiniones if t == 'queja')

    L = [f'📊 *Reporte del día {dia.strftime("%d/%m")} — SELQUET*', '']

    L += ['🛒 *Pedidos*',
          f'• Realizados: {realizados}',
          f'• Cobrados: {len(cobrados)} ({_pesos(monto_cobrado)})',
          f'• Entregados: {entregados}', '']

    L += ['🎉 *Eventos*',
          f'• Solicitudes: {total_ev}',
          f'• Contactadas: {contactadas} de {total_ev}']
    for tipo, nombre, empresa, personas, estado in eventos:
        emp = f' ({empresa})' if empresa else ''
        per = f' · {personas} pers' if personas else ''
        L.append(f'   – {tipo or "evento"}: {nombre}{emp}{per} — {estado}')
    L.append('')

    L += ['🍽️ *Reservas*',
          f'• Mesas reservadas para hoy: {reservas_hoy}', '']

    L += ['💬 *Opiniones*',
          f'• Personas que dieron su opinión: {total_op}',
          f'• 👍 Buenas: {buenas} · 👎 Malas: {malas}']
    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    if base:
        L.append(f'• Ver comentarios del día: {base}/admin/operacion?vista=opiniones&fecha={dia.isoformat()}')

    if cambios:
        L += ['', '🏷️ *Cambios de precio*']
        for nombre, ant, nuevo in cambios:
            L.append(f'• {nombre}: {_pesos(ant)} → {_pesos(nuevo)}')

    return '\n'.join(L)


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
        notificaciones.enviar_email(email, 'Reporte diario — SELQUET', texto)
        enviados += 1
    if not (whatsapps or emails):
        print('[Reporte] No hay jefes configurados (jefe_whatsapp / jefe_email).')
    return {'enviados': enviados, 'texto': texto}


def _lista(valor: str) -> list[str]:
    import re
    return [x.strip() for x in re.split(r'[,\n;]+', valor or '') if x.strip()]
