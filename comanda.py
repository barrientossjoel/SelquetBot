"""Comanda del pedido en PDF (ticket con el look & feel de SELQUET).

Se genera con PyMuPDF (la misma dependencia que la carta) y se sirve en una URL
pública (/pedir/<id>/comanda.pdf) para que el proveedor de WhatsApp la adjunte.
El logo blanco de SELQUET se inserta sobre una banda oscura (header).
"""
from __future__ import annotations

import os

import fitz

from config_store import get_config
from formato import pesos

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGO = os.path.join(_BASE_DIR, 'static', 'selquet-logo.svg')

_ANCHO = 384          # ~13,5 cm: formato ticket
_MARGEN = 28
_HEADER_H = 74
_TINTA = (0.420, 0.122, 0.180)   # #6b1f2e (bordó SELQUET, banda del header)
_ACENTO = (0.690, 0.553, 0.341)  # #b08d57 (dorado SELQUET)
_GRIS = (0.80, 0.80, 0.80)
_GRIS_TX = (0.42, 0.45, 0.50)
_CHIP_BG = (0.965, 0.945, 0.918)  # dorado muy claro para el chip final


def pdf_bytes(pedido) -> bytes:
    """PDF ticket con branding: header con logo, ítems, total y datos de retiro."""
    items = list(pedido.items or [])
    alto = _HEADER_H + 150 + len(items) * 22 + 150
    doc = fitz.open()
    page = doc.new_page(width=_ANCHO, height=alto)
    x0, x1 = _MARGEN, _ANCHO - _MARGEN

    _header(page)
    y = _HEADER_H + 34

    page.insert_text((x0, y), f'COMANDA DE PEDIDO', fontsize=9, fontname='hebo', color=_GRIS_TX)
    page.insert_text((x1 - fitz.get_text_length(f'N° {pedido.id}', 'hebo', 13), y),
                     f'N° {pedido.id}', fontsize=13, fontname='hebo', color=_ACENTO)
    y += 16
    _linea(page, x0, x1, y); y += 24

    for it in items:
        cant = it.get('cantidad', 0)
        nombre = it.get('nombre', '')
        precio = int(it.get('precio', 0))
        page.insert_text((x0, y), f"{cant}x {nombre}", fontsize=12, fontname='helv')
        _derecha(page, x1, y, pesos(precio * cant), 12)
        y += 22

    y += 6; _linea(page, x0, x1, y); y += 26
    page.insert_text((x0, y), 'Total', fontsize=16, fontname='hebo')
    _derecha(page, x1, y, pesos(pedido.total), 16, bold=True, color=_ACENTO)
    y += 20
    page.insert_text((x0, y), 'Takeaway  ·  Pago: Mercado Pago', fontsize=10, fontname='helv', color=_GRIS_TX)
    y += 18; _linea(page, x0, x1, y); y += 26

    for label, val in _datos(pedido):
        page.insert_text((x0, y), label + ':', fontsize=11, fontname='hebo', color=_GRIS_TX)
        page.insert_text((x0 + 92, y), str(val), fontsize=11, fontname='helv')
        y += 20

    y += 16
    _chip(page, x0, y, 'Mostrá esta comanda al retirar tu pedido')
    return doc.tobytes()


_logo_cache = None


def _logo_pdf():
    """El logo como PDF vectorial, forzando el fill blanco (MuPDF no aplica el CSS
    `.st0{fill}` del SVG, así que inyectamos el color inline). Cacheado."""
    global _logo_cache
    if _logo_cache is None:
        with open(_LOGO, 'r', encoding='utf-8') as f:
            txt = f.read().replace('class="st0"', 'fill="#ffffff"')
        svg = fitz.open(stream=txt.encode('utf-8'), filetype='svg')
        _logo_cache = fitz.open('pdf', svg.convert_to_pdf())
    return _logo_cache


def _header(page):
    """Banda oscura con el logo blanco de SELQUET (o el nombre si no está el SVG)."""
    page.draw_rect(fitz.Rect(0, 0, _ANCHO, _HEADER_H), fill=_TINTA, color=_TINTA)
    try:
        # El wordmark ocupa la franja superior del viewBox (595x685): la recortamos.
        clip = fitz.Rect(0, 100, 595, 220)
        rel = clip.height / clip.width
        w = 150
        rect = fitz.Rect(_MARGEN, (_HEADER_H - w * rel) / 2, _MARGEN + w, (_HEADER_H + w * rel) / 2)
        page.show_pdf_page(rect, _logo_pdf(), 0, clip=clip)
    except Exception:
        page.insert_text((_MARGEN, _HEADER_H / 2 + 8), get_config('nombre_local', 'SELQUET'),
                         fontsize=24, fontname='hebo', color=(1, 1, 1))


def _datos(pedido):
    d = []
    if pedido.nombre_cliente:
        d.append(('A nombre de', pedido.nombre_cliente))
    d.append(('Teléfono', pedido.wa_id))
    if pedido.hora_retiro:
        d.append(('Retiro', pedido.hora_retiro.strftime('%H:%M') + ' hs'))
    if pedido.creado_en:
        d.append(('Fecha', pedido.creado_en.strftime('%d/%m/%Y')))
    return d


def _linea(page, x0, x1, y):
    page.draw_line((x0, y), (x1, y), color=_GRIS, width=0.8)


def _derecha(page, x1, y, texto, fontsize, bold=False, color=(0, 0, 0)):
    fontname = 'hebo' if bold else 'helv'
    ancho = fitz.get_text_length(texto, fontname=fontname, fontsize=fontsize)
    page.insert_text((x1 - ancho, y), texto, fontsize=fontsize, fontname=fontname, color=color)


def _chip(page, x, y, texto):
    ancho = fitz.get_text_length(texto, 'hebo', 10)
    page.draw_rect(fitz.Rect(x, y - 13, x + ancho + 24, y + 7), fill=_CHIP_BG,
                   color=_ACENTO, width=0.8, radius=0.3)
    page.insert_text((x + 12, y), texto, fontsize=10, fontname='hebo', color=_ACENTO)
