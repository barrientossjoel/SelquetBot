"""Web pública de pedidos para llevar (/pedir).

El cliente arma el pedido eligiendo del menú (precios del sistema), elige cómo
pagar (MercadoPago o al retirar) y confirma. El pedido se registra en el panel
(solapa Operación) y la pantalla de confirmación ofrece mandarlo por WhatsApp al
local, con un resumen precargado (patrón "click to chat", estilo pedidodirecto).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from urllib.parse import quote

from flask import (Blueprint, abort, redirect, render_template, request,
                   url_for)

import config_store
import pedidos
from database import SessionLocal
from formato import pesos
from models import MenuItem
from telefono import normalizar_ar

pedir_bp = Blueprint('pedir', __name__, template_folder='templates')


def _menu_por_categoria() -> list[tuple[str, list[MenuItem]]]:
    db = SessionLocal()
    try:
        items = (db.query(MenuItem)
                 .filter(MenuItem.disponible.is_(True))
                 .order_by(MenuItem.categoria, MenuItem.nombre).all())
    finally:
        db.close()
    grupos: dict[str, list[MenuItem]] = {}
    for it in items:
        grupos.setdefault(it.categoria or 'General', []).append(it)
    return list(grupos.items())


def _pedido_minimo() -> int:
    from admin.excel_import import limpiar_precio
    return limpiar_precio(config_store.get_config('pedido_minimo', '')) or 0


def _mp_disponible() -> bool:
    return bool(os.getenv('MP_ACCESS_TOKEN', '').strip())


@pedir_bp.route('/pedir', methods=['GET'])
def menu():
    return render_template('pedir/menu.html',
                           nombre_local=config_store.get_config('nombre_local', 'SELQUET'),
                           categorias=_menu_por_categoria(),
                           pedido_minimo=_pedido_minimo(),
                           mp_disponible=_mp_disponible(),
                           error=None, form={})


@pedir_bp.route('/pedir', methods=['POST'])
def crear():
    form = request.form
    nombre = (form.get('nombre') or '').strip()
    telefono = normalizar_ar(form.get('telefono'))
    metodo_pago = 'mercadopago' if (form.get('metodo_pago') == 'mercadopago' and _mp_disponible()) else 'efectivo'
    notas = (form.get('notas') or '').strip() or None

    try:
        crudos = json.loads(form.get('items_json') or '[]')
    except json.JSONDecodeError:
        crudos = []
    items_pedido = [{'nombre': c.get('nombre'), 'cantidad': c.get('cantidad')}
                    for c in crudos if c.get('nombre') and int(c.get('cantidad') or 0) > 0]

    error = None
    if not nombre or not telefono:
        error = 'Completá tu nombre y tu teléfono.'
    elif not items_pedido:
        error = 'Elegí al menos un producto.'
    else:
        armado = pedidos.armar_pedido(items_pedido)
        if not armado['ok']:
            error = armado['mensaje']

    if error:
        return render_template('pedir/menu.html',
                               nombre_local=config_store.get_config('nombre_local', 'SELQUET'),
                               categorias=_menu_por_categoria(),
                               pedido_minimo=_pedido_minimo(),
                               mp_disponible=_mp_disponible(),
                               error=error, form=form), 400

    res = pedidos.registrar_web(
        nombre=nombre, telefono=telefono,
        items=armado['items'], total=armado['total'],
        hora_retiro=_parse_hora(form.get('hora_retiro')),
        metodo_pago=metodo_pago, notas=notas,
    )
    if not res['ok']:
        return render_template('pedir/menu.html',
                               nombre_local=config_store.get_config('nombre_local', 'SELQUET'),
                               categorias=_menu_por_categoria(),
                               pedido_minimo=_pedido_minimo(),
                               mp_disponible=_mp_disponible(),
                               error=res.get('mensaje', 'No pude registrar el pedido.'),
                               form=form), 502
    return redirect(url_for('pedir.confirmacion', pid=res['pedido_id']))


@pedir_bp.route('/pedir/<int:pid>', methods=['GET'])
def confirmacion(pid):
    pedido = pedidos.obtener(pid)
    if not pedido or pedido.canal != 'web':
        abort(404)
    mp_status = request.args.get('status') or request.args.get('collection_status')
    pagado = pedido.estado in ('pagado', 'preparado', 'retirado') or mp_status == 'approved'
    return render_template('pedir/confirmacion.html',
                           nombre_local=config_store.get_config('nombre_local', 'SELQUET'),
                           p=pedido, pagado=pagado,
                           wa_link=_wa_link(pedido),
                           wa_confirmacion=_wa_confirmacion_link(pedido),
                           link_pago=_link_pago(pedido))


# ─── helpers ───

def _parse_hora(valor: str | None) -> datetime | None:
    """'HH:MM' → datetime de hoy a esa hora (para la vista del local)."""
    try:
        h, m = (int(x) for x in (valor or '').split(':'))
        return datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
    except (ValueError, TypeError):
        return None


def _base_url() -> str:
    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    return base or request.host_url.rstrip('/')


def _link_pago(pedido) -> str | None:
    """Reconstruye el link de pago de MercadoPago si el pedido está sin pagar."""
    if pedido.metodo_pago != 'mercadopago' or pedido.estado != 'pendiente_pago' or not pedido.mp_preference_id:
        return None
    return f'https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id={pedido.mp_preference_id}'


def _numero_bot() -> str | None:
    """Número de WhatsApp del bot (para que el cliente le escriba tras pagar)."""
    n = (os.getenv('TWILIO_WA_NUMBER') or '').replace('whatsapp:', '').replace('+', '').strip()
    return n or None


def _wa_confirmacion_link(pedido) -> str | None:
    """Link wa.me AL BOT para que el cliente confirme el pago y siga la charla
    (el bot le pregunta si quiere algo más / algún comentario)."""
    destino = _numero_bot()
    if not destino:
        return None
    hora = f" (retiro {pedido.hora_retiro.strftime('%H:%M')})" if pedido.hora_retiro else ""
    texto = f"¡Hola! Ya pagué mi pedido Nº {pedido.id} ✅{hora}. ¿Está todo listo?"
    return f'https://wa.me/{destino}?text={quote(texto)}'


def _wa_link(pedido) -> str | None:
    """Link wa.me al WhatsApp del local con el resumen del pedido precargado."""
    destino = normalizar_ar(config_store.get_config('whatsapp_local', ''))
    if not destino:
        return None
    lineas = [f'Hola, te paso mi pedido. Espero confirmación | Pedido Nº {pedido.id}', '']
    lineas += [f"{it['cantidad']}x {it['nombre']}" for it in pedido.items]
    lineas += ['', f'Total: {pesos(pedido.total)}']
    if pedido.hora_retiro:
        lineas.append(f"Retiro: {pedido.hora_retiro.strftime('%H:%M')}")
    lineas.append('Pago: ' + ('MercadoPago' if pedido.metodo_pago == 'mercadopago' else 'al retirar'))
    lineas.append(f'A nombre de: {pedido.nombre_cliente}')
    lineas.append(f'{_base_url()}/pedir/{pedido.id}')
    return f'https://wa.me/{destino}?text={quote(chr(10).join(lineas))}'
