"""Carta en PDF con precios actualizados desde el sistema (Opción B).

Sobre el PDF de diseño original se detecta cada precio por su posición y, si el
nombre del plato matchea un producto del menú (exacto o muy parecido), se
reemplaza SOLO el número por el precio actual de la DB. Los que no matchean con
confianza quedan como están impresos (nunca se pone un precio incorrecto).
Se cachea por "huella" del menú: se regenera solo cuando cambian los precios.
"""
from __future__ import annotations

import difflib
import os
import re
import unicodedata

import fitz

from database import SessionLocal
from models import MenuItem

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(_BASE_DIR, 'assets', 'Carta_Selquet.pdf')

_PRECIO = re.compile(r'^\d{1,3}(?:\.\d{3})+$')   # 4.000, 17.500, 1.780.000
_DOTS = re.compile(r'^[.…]+$')
_UMBRAL_FUZZY = 0.90

_cache = {'fingerprint': None, 'bytes': None}


def existe() -> bool:
    return os.path.isfile(PDF_PATH)


def ruta_pdf() -> str:
    return PDF_PATH


def link_publico() -> str:
    """URL del PDF con un ?v= que cambia cuando cambian los precios, así Meta
    (que cachea el documento por URL) baja una copia fresca en cada cambio."""
    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    return f'{base}/carta.pdf?v={_version()}' if base else ''


def _version() -> str:
    import hashlib
    huella = repr(sorted((m.id, m.precio) for m in _menu())).encode()
    return hashlib.md5(huella).hexdigest()[:10]


def pdf_bytes() -> bytes:
    """PDF con precios del sistema. Cacheado por huella (id, precio) del menú."""
    menu = _menu()
    fingerprint = tuple(sorted((m.id, m.precio) for m in menu))
    if _cache['fingerprint'] == fingerprint and _cache['bytes'] is not None:
        return _cache['bytes']
    data = _generar(menu)
    _cache['fingerprint'], _cache['bytes'] = fingerprint, data
    return data


def cobertura() -> dict:
    """Diagnóstico: cuántos precios del PDF matchean con el menú."""
    menu = _menu()
    index = _indexar(menu)
    doc = fitz.open(PDF_PATH)
    total = matcheados = 0
    for page in doc:
        words = page.get_text('words')
        for pw in [w for w in words if _PRECIO.match(w[4])]:
            total += 1
            if _match(_nombre_izquierda(words, pw), index) is not None:
                matcheados += 1
    return {'total': total, 'matcheados': matcheados}


def _menu():
    db = SessionLocal()
    try:
        return db.query(MenuItem).all()
    finally:
        db.close()


def _indexar(menu):
    index = {}
    for m in menu:
        index.setdefault(_norm(m.nombre), m)
    return index


def _generar(menu) -> bytes:
    index = _indexar(menu)
    doc = fitz.open(PDF_PATH)
    for page in doc:
        words = page.get_text('words')
        reemplazos = []
        for pw in [w for w in words if _PRECIO.match(w[4])]:
            item = _match(_nombre_izquierda(words, pw), index)
            if item is None:
                continue
            nuevo = _fmt(item.precio)
            if nuevo != pw[4]:
                reemplazos.append((fitz.Rect(pw[:4]), nuevo))
        # 1) borrar los precios viejos (redacción real)
        for rect, _ in reemplazos:
            page.add_redact_annot(rect, fill=(1, 1, 1))
        if reemplazos:
            page.apply_redactions()
        # 2) escribir los nuevos, alineados a la derecha en el mismo lugar
        for rect, texto in reemplazos:
            _escribir(page, rect, texto)
    return doc.tobytes()


def _escribir(page, rect, texto):
    fontsize = rect.height * 0.82
    ancho = fitz.get_text_length(texto, fontname='helv', fontsize=fontsize)
    page.insert_text((rect.x1 - ancho, rect.y1 - rect.height * 0.16),
                     texto, fontsize=fontsize, fontname='helv', color=(0, 0, 0))


def _nombre_izquierda(words, pw):
    """Nombre del plato: palabras en la misma banda vertical, a la izquierda,
    misma columna; sin puntitos de relleno, sin '$' ni otros precios."""
    cy = (pw[1] + pw[3]) / 2
    cand = [w for w in words
            if w[0] < pw[0] and abs(((w[1] + w[3]) / 2) - cy) < 6 and w[0] > pw[0] - 380
            and not _DOTS.match(w[4]) and w[4] != '$' and not _PRECIO.match(w[4])]
    cand.sort(key=lambda w: w[0])
    return ' '.join(w[4] for w in cand).strip()


def _match(nombre, index):
    n = _norm(nombre)
    if not n:
        return None
    if n in index:
        return index[n]
    mejor, score = None, 0.0
    for clave, item in index.items():
        r = difflib.SequenceMatcher(None, n, clave).ratio()
        if r > score:
            score, mejor = r, item
    return mejor if score >= _UMBRAL_FUZZY else None


def _norm(s):
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', ' ', re.sub(r'\s+', ' ', s)).strip()


def _fmt(n):
    return f'{int(n):,}'.replace(',', '.')   # 8500 -> '8.500' (sin $, como en el PDF)
