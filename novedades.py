"""Novedades del panel para el aviso pop-up del navegador.

Cada tipo de novedad (pedido, reserva, evento) es una `Fuente`. Para sumar un
tipo nuevo alcanza con agregar una Fuente a FUENTES: la ruta y el JS del front
son genéricos y no hay que tocarlos (Open/Closed).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from database import SessionLocal
from formato import pesos
from models import Pedido, Reserva, SolicitudEvento


@dataclass(frozen=True)
class Fuente:
    clave: str                              # id estable para el front (localStorage)
    titulo: str                             # título del aviso
    modelo: type                            # modelo SQLAlchemy (con .id)
    describir: Callable[[object], str]      # registro -> texto corto del aviso


def _describir_pedido(p) -> str:
    return f'{p.nombre_cliente or p.wa_id} · {pesos(p.total)}'


def _describir_reserva(r) -> str:
    txt = f'{r.nombre or r.wa_id} · {r.personas} pers'
    return txt + (f' · {r.fecha_hora.strftime("%d/%m %H:%M")}' if r.fecha_hora else '')


def _describir_evento(e) -> str:
    txt = f'{e.tipo_evento or "evento"} · {e.nombre_contacto or e.wa_id}'
    return txt + (f' · {e.cantidad_personas} pers' if e.cantidad_personas else '')


FUENTES: tuple[Fuente, ...] = (
    Fuente('pedidos',  'Nuevo pedido',              Pedido,          _describir_pedido),
    Fuente('reservas', 'Nueva reserva',             Reserva,         _describir_reserva),
    Fuente('eventos',  'Nueva solicitud de evento', SolicitudEvento, _describir_evento),
)


def estado() -> dict:
    """Último registro de cada fuente: {clave: {max_id, titulo, label}}.
    El navegador compara `max_id` con lo ya visto y avisa si hay algo nuevo."""
    db = SessionLocal()
    try:
        return {f.clave: _snapshot(f, db.query(f.modelo).order_by(f.modelo.id.desc()).first())
                for f in FUENTES}
    finally:
        db.close()


def _snapshot(fuente: Fuente, ultimo) -> dict:
    return {
        'max_id': ultimo.id if ultimo else 0,
        'titulo': fuente.titulo,
        'label': fuente.describir(ultimo) if ultimo else None,
    }
