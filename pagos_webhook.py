"""Webhook de MercadoPago: confirma el pago y manda el pedido a cocinar.

MP avisa (query o body) con el id del pago; consultamos su estado y, si está
'approved', pasamos el pedido a 'pagado' y le avisamos al cliente por WhatsApp
(su ventana de 24h está abierta porque el pedido lo inició él).
"""
from __future__ import annotations

import threading
import traceback

from flask import Blueprint, request

import pagos
import pedidos

pagos_bp = Blueprint('pagos', __name__)


@pagos_bp.route('/webhook/mercadopago', methods=['GET', 'POST'])
def webhook_mercadopago():
    payment_id, topic = _extraer_notificacion(request)
    if payment_id and 'payment' in (topic or 'payment'):
        _procesar_async(payment_id)
    return 'OK', 200


def _extraer_notificacion(req):
    """MP notifica de varias formas: ?type=payment&data.id=, ?topic=payment&id=,
    o un body JSON {type, data:{id}}."""
    payment_id = req.args.get('data.id') or req.args.get('id') or ''
    topic = req.args.get('type') or req.args.get('topic') or ''
    if not payment_id:
        body = req.get_json(silent=True) or {}
        payment_id = str((body.get('data') or {}).get('id') or '')
        topic = body.get('type') or topic
    return payment_id, topic


def _procesar_async(payment_id):
    threading.Thread(target=_procesar, args=(payment_id,), daemon=True).start()


def _procesar(payment_id):
    try:
        info = pagos.consultar_pago(payment_id)
        if not info or info.get('status') != 'approved':
            return
        pedido_id = pedidos.marcar_pagado(info.get('external_reference'), payment_id)
        if pedido_id:
            pedido = pedidos.obtener(pedido_id)
            if pedido:
                from whatsapp.providers import get_provider
                provider = get_provider()
                hr = pedido.hora_retiro.strftime('%H:%M') if pedido.hora_retiro else 'el horario acordado'
                provider.send_message(
                    pedido.wa_id, f'¡Pago confirmado! 🎉 Tu pedido ya está en cocina. Lo retirás a las {hr}.')
                # Comanda estilo ticket para que la muestre al retirar.
                provider.send_message(pedido.wa_id, pedidos.comanda_texto(pedido))
    except Exception as e:
        print(f'[MP Webhook] Error procesando pago {payment_id}: {e}')
        traceback.print_exc()
