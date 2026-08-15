"""Seguimiento post-pedido.

Unas horas después de un pedido, el bot le escribe al cliente para preguntarle
cómo le fue. La respuesta la toma el flujo normal de OPINIONES del bot (que la
guarda con registrar_opinion), y así se juntan datos para estadísticas.

Ojo con WhatsApp: un mensaje proactivo (fuera de una conversación abierta de 24 h)
requiere una PLANTILLA aprobada. Funciona directo con clientes que venían
chateando con el bot; para pedidos de la web puede necesitar plantilla.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import config_store
from database import SessionLocal
from models import Pedido

HORAS_DESPUES = 3


def enviar_pendientes() -> int:
    """Manda el '¿cómo te fue?' a los pedidos de hace >= HORAS_DESPUES que aún no
    lo recibieron. Se llama periódicamente desde el scheduler."""
    corte = datetime.now() - timedelta(hours=HORAS_DESPUES)
    db = SessionLocal()
    try:
        pendientes = (db.query(Pedido)
                      .filter(Pedido.seguimiento_enviado.is_(None),
                              Pedido.creado_en <= corte,
                              Pedido.estado != 'cancelado')
                      .all())
        objetivos = [(p.id, p.wa_id, p.nombre_cliente) for p in pendientes]
    finally:
        db.close()
    if not objetivos:
        return 0

    from whatsapp.providers import get_provider
    provider = get_provider()
    nombre_local = config_store.get_config('nombre_local', 'SELQUET')

    enviados = 0
    for pedido_id, wa_id, nombre in objetivos:
        saludo = f"¡Hola{(' ' + nombre) if nombre else ''}!"
        texto = (f"{saludo} Somos {nombre_local} 🙂 ¿Cómo te fue con tu pedido? "
                 f"Contanos qué te pareció, tu opinión nos ayuda un montón 🙏")
        try:
            provider.send_message(wa_id, texto)
            # Guardamos el mensaje en el historial para que, cuando el cliente
            # responda, el bot tenga contexto: lo trate como OPINIÓN (la registra)
            # y NO arranque una conversación nueva saludándolo de cero.
            from whatsapp.conversaciones import guardar_turno
            guardar_turno(wa_id, 'assistant', [{'type': 'text', 'text': texto}])
        except Exception as e:
            print(f"[Seguimiento] Error enviando a {wa_id}: {e}")
        _marcar_enviado(pedido_id)   # marca igual, para no reintentar en loop
        enviados += 1
    print(f"[Seguimiento] {enviados} mensajes de seguimiento enviados")
    return enviados


def _marcar_enviado(pedido_id: int) -> None:
    db = SessionLocal()
    try:
        pedido = db.get(Pedido, pedido_id)
        if pedido:
            pedido.seguimiento_enviado = datetime.now()
            db.commit()
    finally:
        db.close()
