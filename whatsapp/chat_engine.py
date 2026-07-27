"""Motor de chat conversacional del bot de SELQUET (Claude, con tool use).

Los datos del local (info, menú, FAQs) se inyectan desde la DB (contexto.py).
Las ACCIONES (reservas, opiniones) se resuelven con tools (tools.py) en un loop
agéntico. Los pedidos para llevar llegan en el próximo slice.
"""
from __future__ import annotations

import json
import os
import traceback
from datetime import date

from anthropic import Anthropic

from config_store import get_config
from .contexto import build_datos_local
from .conversaciones import cargar_historial, guardar_turno
from .tools import TOOLS, ejecutar

MODELO = os.getenv('CLAUDE_MODEL', 'claude-haiku-4-5')
MAX_TOKENS_RESPUESTA = 600
MAX_ITERACIONES = 5

SYSTEM_PERSONA = """Sos el asistente de WhatsApp del restaurante {nombre_local}.
Hablás en español rioplatense, cálido y breve (2-4 líneas, es WhatsApp).

CÓMO CONVERSÁS
- Conversación abierta y natural. Entendés como escriba la persona, con errores de tipeo o abreviado.
- NUNCA hagas menús numerados ni preguntas cerradas tipo "respondé 1, 2 o 3".
- Si falta un dato para avanzar, pedilo natural y de a uno.
- Usá SIEMPRE los datos que te paso abajo. Nunca inventes precios, horarios ni disponibilidad. Si no sabés algo, decilo con honestidad y ofrecé que se acerquen o llamen.
- Usá emojis con moderación (1-2 por mensaje, solo si suman).

RESERVAS
- Las reservas comunes son para grupos chicos que entran en una mesa. Para reservar necesitás fecha, hora y cantidad de personas (y el nombre). Si falta algo, pedilo.
- Resolvé fechas relativas ("mañana", "el sábado", "hoy") según la fecha de hoy.
- Si el cliente pregunta si hay lugar, usá consultar_disponibilidad. Para confirmar, usá crear_reserva.
- La reserva queda pendiente de confirmación del local: decíselo al cliente.
- IMPORTANTE: si es un grupo grande (8 o más personas) o mencionan un festejo/celebración/reunión (cumpleaños, corporativo, aniversario, etc.), NO es una reserva común y NO le digas que llame al local: pasá al flujo de EVENTOS (abajo) y tomale los datos.

CARTA
- Si piden ver la carta, el menú completo o "la carta en PDF", usá enviar_carta (les manda el PDF) y avisales con una frase corta.
- Para un precio o plato puntual NO mandes el PDF: respondé directo desde el menú.

EVENTOS (corporativos, privados y sociales)
- El local hace eventos: corporativos (desayunos de negocios, presentaciones, workshops, team building, networking), privados y sociales (cumpleaños, casamientos, aniversarios, bautismos, despedidas). Un grupo grande (8+ personas) también se maneja como evento.
- Cuando detectes un evento, hacé el formulario: tomá los datos conversando y de a uno (no todos de golpe), preguntá qué tipo de evento es, nombre de quien organiza (y empresa si es corporativo), fecha/horario estimado, cantidad aproximada de personas, y requerimientos (catering, proyector/sonido, disposición de mesas, presupuesto). Nunca cierres con "llamá al local": la idea es tomarle los datos para que el equipo lo contacte.
- SI ES UN EVENTO CORPORATIVO: pedile además un dato de contacto (teléfono o email) y EN QUÉ HORARIO prefiere que lo llamen para coordinar, y explicale que el equipo de eventos lo va a contactar en ese horario para explicarle cómo son los pasos.
- Cuando tengas los datos, usá crear_solicitud_evento (si es corporativo, incluí el contacto y el horario_contacto). Confirmale que quedó registrada y que el equipo se va a contactar.

OPINIONES
- Si el cliente deja un elogio o una queja, guardalo con registrar_opinion y agradecé.

PEDIDOS PARA LLEVAR
- Tomá los productos con cantidades y preguntá a qué hora lo va a retirar. Con eso usá crear_pedido.
- crear_pedido calcula el total, valida el pedido mínimo y devuelve un link de pago: pasáselo al cliente.
- Aclarale SIEMPRE que el pedido se manda a cocinar recién cuando paga por ese link.
- No listes todo el menú en texto (es largo): guialo por lo que busca o por categoría.

Fecha de hoy: {fecha_hoy}"""


def responder(telefono: str, texto: str) -> str:
    """Recibe el mensaje del cliente y devuelve la respuesta del bot."""
    try:
        return _loop(telefono, texto)
    except Exception as e:
        print(f"[SELQUET ChatEngine] Error: {e}")
        traceback.print_exc()
        return _RESPUESTA_ERROR


def _loop(telefono: str, texto: str) -> str:
    client = Anthropic()
    system = _build_system()
    historial = cargar_historial(telefono)
    historial.append({'role': 'user', 'content': texto})

    for _ in range(MAX_ITERACIONES):
        resp = client.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS_RESPUESTA,
            system=system, tools=TOOLS, messages=historial,
        )
        historial.append({'role': 'assistant', 'content': resp.content})

        if resp.stop_reason != 'tool_use':
            final = _extraer_texto(resp.content) or _RESPUESTA_VACIA
            _persistir(telefono, texto, final)
            return final

        historial.append({'role': 'user', 'content': _correr_tools(resp.content, telefono)})

    _persistir(telefono, texto, _RESPUESTA_TIMEOUT)
    return _RESPUESTA_TIMEOUT


def _correr_tools(content, telefono):
    resultados = []
    for bloque in content:
        if getattr(bloque, 'type', None) == 'tool_use':
            resultado = ejecutar(bloque.name, bloque.input or {}, telefono)
            resultados.append({
                'type': 'tool_result',
                'tool_use_id': bloque.id,
                'content': json.dumps(resultado, ensure_ascii=False, default=str),
            })
    return resultados


def _build_system():
    """Personalidad fija + datos del local leídos de la DB."""
    persona = SYSTEM_PERSONA.format(
        nombre_local=get_config('nombre_local', 'SELQUET'),
        fecha_hoy=date.today().isoformat(),
    )
    partes = [persona]
    bienvenida = get_config('mensaje_bienvenida', '').strip()
    if bienvenida:
        partes.append('MENSAJE DE BIENVENIDA (usalo para presentarte al saludar y, sobre todo, cuando '
                      'alguien quiere hacer un pedido; adaptalo con naturalidad, no hace falta repetirlo textual):\n'
                      + bienvenida)
    partes.append(build_datos_local())
    return [{'type': 'text', 'text': '\n\n'.join(partes), 'cache_control': {'type': 'ephemeral'}}]


def _persistir(telefono, texto_user, texto_final):
    """Guarda solo el texto del user y la respuesta final (sin bloques
    tool_use/tool_result) para que el historial futuro sea liviano y coherente."""
    guardar_turno(telefono, 'user', [{'type': 'text', 'text': texto_user}])
    guardar_turno(telefono, 'assistant', [{'type': 'text', 'text': texto_final}])


def _extraer_texto(content) -> str:
    if isinstance(content, str):
        return content
    partes = (getattr(b, 'text', None) for b in (content or []) if getattr(b, 'type', None) == 'text')
    return '\n'.join(p for p in partes if p).strip()


_RESPUESTA_VACIA = "Perdón, no te entendí bien. ¿Me lo repetís?"
_RESPUESTA_TIMEOUT = "Se me complicó procesar eso. ¿Lo intentamos de otra forma?"
_RESPUESTA_ERROR = "Uy, tuve un problema para responderte. Probá de nuevo en un ratito 🙏"
