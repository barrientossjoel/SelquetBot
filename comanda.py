"""Comanda del pedido en PDF (ticket) para enviársela al comprador por WhatsApp.

Se genera con PyMuPDF (la misma dependencia que la carta) y se sirve en una URL
pública (/pedir/<id>/comanda.pdf) para que el proveedor de WhatsApp la adjunte.
"""
from __future__ import annotations

import fitz

from config_store import get_config
from formato import pesos

_ANCHO = 384        # ~13,5 cm: formato ticket
_MARGEN = 28
_GRIS = (0.8, 0.8, 0.8)


def pdf_bytes(pedido) -> bytes:
    """PDF ticket con el detalle del pedido (ítems, total, datos de retiro)."""
    nombre_local = get_config('nombre_local', 'SELQUET')
    items = list(pedido.items or [])
    alto = 200 + len(items) * 22 + 150
    doc = fitz.open()
    page = doc.new_page(width=_ANCHO, height=alto)
    x0, x1 = _MARGEN, _ANCHO - _MARGEN
    y = 50

    page.insert_text((x0, y), nombre_local, fontsize=24, fontname='hebo')
    y += 20
    page.insert_text((x0, y), f'Comanda de pedido  -  N {pedido.id}', fontsize=11, fontname='helv')
    y += 14
    _linea(page, x0, x1, y); y += 24

    for it in items:
        cant = it.get('cantidad', 0)
        nombre = it.get('nombre', '')
        precio = int(it.get('precio', 0))
        page.insert_text((x0, y), f"{cant}x {nombre}", fontsize=12, fontname='helv')
        _derecha(page, x1, y, pesos(precio * cant), 12)
        y += 22

    y += 4; _linea(page, x0, x1, y); y += 26
    page.insert_text((x0, y), 'Total', fontsize=15, fontname='hebo')
    _derecha(page, x1, y, pesos(pedido.total), 15, bold=True)
    y += 22
    page.insert_text((x0, y), 'Takeaway  -  Pago: Mercado Pago', fontsize=11, fontname='helv')
    y += 16; _linea(page, x0, x1, y); y += 26

    for label, val in _datos(pedido):
        page.insert_text((x0, y), f'{label}: {val}', fontsize=11, fontname='helv')
        y += 19

    y += 14
    page.insert_text((x0, y), 'Mostra esta comanda al retirar tu pedido', fontsize=11, fontname='hebo')
    return doc.tobytes()


def _datos(pedido):
    d = []
    if pedido.nombre_cliente:
        d.append(('A nombre de', pedido.nombre_cliente))
    d.append(('Telefono', pedido.wa_id))
    if pedido.hora_retiro:
        d.append(('Retiro', pedido.hora_retiro.strftime('%H:%M') + ' hs'))
    if pedido.creado_en:
        d.append(('Fecha', pedido.creado_en.strftime('%d/%m/%Y')))
    return d


def _linea(page, x0, x1, y):
    page.draw_line((x0, y), (x1, y), color=_GRIS, width=0.8)


def _derecha(page, x1, y, texto, fontsize, bold=False):
    fontname = 'hebo' if bold else 'helv'
    ancho = fitz.get_text_length(texto, fontname=fontname, fontsize=fontsize)
    page.insert_text((x1 - ancho, y), texto, fontsize=fontsize, fontname=fontname)
