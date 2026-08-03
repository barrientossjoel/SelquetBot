"""Integración con MercadoPago (Checkout Pro).

Token por env (`MP_ACCESS_TOKEN`): TEST-... para la etapa de prueba, APP_USR-...
en producción. Pasar de uno al otro es solo cambiar el .env, sin tocar código.
`MP_BASE_URL` es la URL pública del backend (en sandbox, la de ngrok) para el
webhook y las back_urls.
"""
from __future__ import annotations

import os

import requests

MP_API = 'https://api.mercadopago.com'


def crear_preferencia(items: list[dict], external_reference, back_url=None) -> dict:
    """items: [{'title', 'quantity', 'unit_price'}]. `back_url` es a dónde vuelve
    el cliente tras pagar. Devuelve {ok, link, preference_id}."""
    token = os.getenv('MP_ACCESS_TOKEN', '')
    if not token:
        return {'ok': False, 'mensaje': 'MercadoPago no está configurado (falta MP_ACCESS_TOKEN).'}

    payload = {
        'items': [{
            'title': i['title'],
            'quantity': int(i['quantity']),
            'unit_price': float(i['unit_price']),
            'currency_id': 'ARS',
        } for i in items],
        'external_reference': str(external_reference),
    }
    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    if base:
        payload['notification_url'] = f'{base}/webhook/mercadopago'
    destino = back_url or base
    if destino:
        payload['back_urls'] = {'success': destino, 'failure': destino, 'pending': destino}
    if back_url:
        payload['auto_return'] = 'approved'   # vuelve solo al sitio tras aprobar

    try:
        r = requests.post(f'{MP_API}/checkout/preferences', json=payload,
                          headers={'Authorization': f'Bearer {token}'}, timeout=15)
        if r.status_code not in (200, 201):
            print(f'[MP] Error creando preferencia: {r.status_code} - {r.text}')
            return {'ok': False, 'mensaje': 'No pude generar el link de pago.'}
        data = r.json()
        return {'ok': True, 'preference_id': data['id'],
                'link': data.get('init_point') or data.get('sandbox_init_point')}
    except Exception as e:
        print(f'[MP] Error de red creando preferencia: {e}')
        return {'ok': False, 'mensaje': 'No pude generar el link de pago.'}


def consultar_pago(payment_id) -> dict | None:
    """Devuelve el pago de MercadoPago (o None). El estado 'approved' = pagado."""
    token = os.getenv('MP_ACCESS_TOKEN', '')
    if not token:
        return None
    try:
        r = requests.get(f'{MP_API}/v1/payments/{payment_id}',
                         headers={'Authorization': f'Bearer {token}'}, timeout=15)
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f'[MP] Error consultando pago: {e}')
        return None
