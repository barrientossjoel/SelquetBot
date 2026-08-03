"""Dominio de pedidos para llevar.

Arma el pedido desde el menú de la DB (match por nombre normalizado), valida el
pedido mínimo, lo crea en estado 'pendiente_pago' y genera el link de pago.
El webhook de MercadoPago lo pasa a 'pagado' (a cocinar).
"""
from __future__ import annotations

import os
import unicodedata
from datetime import datetime

import notificaciones_panel
import pagos
from config_store import get_config
from database import SessionLocal
from formato import pesos
from models import MenuItem, Pedido


def armar_pedido(items_pedido: list[dict]) -> dict:
    """items_pedido: [{'nombre', 'cantidad'}]. Devuelve {ok, items, total} o el motivo."""
    db = SessionLocal()
    try:
        menu = db.query(MenuItem).filter(MenuItem.disponible.is_(True)).all()
    finally:
        db.close()
    por_nombre = {_norm(m.nombre): m for m in menu}

    detalle, total, no_encontrados = [], 0, []
    for it in items_pedido:
        nombre = it.get('nombre', '')
        cantidad = max(1, int(it.get('cantidad') or 1))
        m = por_nombre.get(_norm(nombre)) or _match_parcial(menu, _norm(nombre))
        if m is None:
            no_encontrados.append(nombre)
            continue
        detalle.append({'nombre': m.nombre, 'cantidad': cantidad, 'precio': m.precio})
        total += m.precio * cantidad

    if no_encontrados:
        return {'ok': False, 'motivo': 'no_encontrado', 'no_encontrados': no_encontrados,
                'mensaje': 'No encontré en el menú: ' + ', '.join(no_encontrados)}
    if not detalle:
        return {'ok': False, 'motivo': 'vacio', 'mensaje': 'El pedido está vacío.'}

    minimo = _pedido_minimo()
    if minimo and total < minimo:
        return {'ok': False, 'motivo': 'minimo', 'total': total, 'minimo': minimo,
                'mensaje': f'El pedido mínimo para llevar es ${minimo:,}'.replace(',', '.') +
                           f' y el tuyo suma ${total:,}'.replace(',', '.') + '. Agregá algo más.'}
    return {'ok': True, 'items': detalle, 'total': total}


def crear_con_link(wa_id: str, items: list[dict], total: int, hora_retiro: datetime | None) -> dict:
    """Crea el pedido pendiente de pago y devuelve el link de MercadoPago."""
    db = SessionLocal()
    try:
        pedido = Pedido(wa_id=wa_id, items=items, total=total,
                        estado='pendiente_pago', hora_retiro=hora_retiro)
        db.add(pedido)
        db.commit()
        pedido_id = pedido.id
    finally:
        db.close()

    pref = pagos.crear_preferencia(
        [{'title': i['nombre'], 'quantity': i['cantidad'], 'unit_price': i['precio']} for i in items],
        external_reference=pedido_id,
    )
    if not pref['ok']:
        return pref

    db = SessionLocal()
    try:
        pedido = db.get(Pedido, pedido_id)
        pedido.mp_preference_id = pref['preference_id']
        db.commit()
    finally:
        db.close()
    return {'ok': True, 'pedido_id': pedido_id, 'link': pref['link'], 'total': total,
            'mensaje': 'Pedido listo. Pasale el link de pago; se manda a cocinar cuando pague.'}


def registrar_web(nombre: str, telefono: str, items: list[dict], total: int,
                  hora_retiro: datetime | None, metodo_pago: str,
                  notas: str | None) -> dict:
    """Crea un pedido hecho desde la web (/pedir). `items` ya viene validado por
    armar_pedido (con precios de la DB). Si el pago es MercadoPago, genera el
    link; si es al retirar, el pedido entra 'confirmado' (en firme)."""
    es_mp = metodo_pago == 'mercadopago'
    db = SessionLocal()
    try:
        pedido = Pedido(
            wa_id=telefono, nombre_cliente=nombre, canal='web',
            items=items, total=total, metodo_pago=metodo_pago, notas=notas,
            hora_retiro=hora_retiro,
            estado='pendiente_pago' if es_mp else 'confirmado',
        )
        db.add(pedido)
        db.commit()
        pedido_id = pedido.id
    finally:
        db.close()

    notificaciones_panel.crear('pedido', f'Nuevo pedido web: {nombre} · {pesos(total)}')

    if not es_mp:
        return {'ok': True, 'pedido_id': pedido_id, 'estado': 'confirmado', 'link': None}

    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    back_url = f'{base}/pedir/{pedido_id}?pago=ok' if base else None
    pref = pagos.crear_preferencia(
        [{'title': i['nombre'], 'quantity': i['cantidad'], 'unit_price': i['precio']} for i in items],
        external_reference=pedido_id, back_url=back_url,
    )
    if not pref['ok']:
        return {'ok': False, 'pedido_id': pedido_id, 'mensaje': pref.get('mensaje', 'No pude generar el link de pago.')}

    db = SessionLocal()
    try:
        db.get(Pedido, pedido_id).mp_preference_id = pref['preference_id']
        db.commit()
    finally:
        db.close()
    return {'ok': True, 'pedido_id': pedido_id, 'estado': 'pendiente_pago', 'link': pref['link']}


def obtener(pedido_id: int) -> Pedido | None:
    db = SessionLocal()
    try:
        return db.get(Pedido, pedido_id)
    finally:
        db.close()


def marcar_pagado(external_reference, payment_id) -> tuple[str | None, datetime | None]:
    """Pasa el pedido a 'pagado'. Devuelve (wa_id, hora_retiro) para avisar al cliente."""
    try:
        pedido_id = int(external_reference)
    except (TypeError, ValueError):
        return None, None
    db = SessionLocal()
    try:
        pedido = db.get(Pedido, pedido_id)
        if pedido and pedido.estado == 'pendiente_pago':
            pedido.estado = 'pagado'
            pedido.mp_payment_id = str(payment_id)
            db.commit()
            return pedido.wa_id, pedido.hora_retiro
        return None, None
    finally:
        db.close()


def _pedido_minimo() -> int:
    from admin.excel_import import limpiar_precio
    return limpiar_precio(get_config('pedido_minimo', '')) or 0


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', (s or '').lower())
    return ''.join(c for c in s if not unicodedata.combining(c)).strip()


def _match_parcial(menu, nq: str):
    if not nq:
        return None
    hits = [m for m in menu if nq in _norm(m.nombre)]
    return hits[0] if len(hits) == 1 else None
