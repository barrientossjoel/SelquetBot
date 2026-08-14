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

import eventos
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

SALUDO / BIENVENIDA
- Cuando alguien te saluda por primera vez o pregunta genéricamente qué ofrecen / cómo pedir, presentate breve y útil (2-4 líneas, no es un formulario). Usando los datos reales de abajo, incluí: los horarios de atención; que se puede pedir para llevar por la web con el link {link_pedidos}; y que el retiro es a partir de 30 minutos y el pago del takeaway es solo con Mercado Pago.
- No inventes descuentos, delivery a domicilio ni datos que no figuren abajo.

REGLA DE ORO — REGISTRAR ACCIONES (CRÍTICA)
- Una reserva o un evento SOLO quedan registrados si llamás a la tool que corresponde (crear_reserva / crear_solicitud_evento) y te devuelve ok. Guardar datos con guardar_dato_evento NO registra nada.
- PROHIBIDO decir "quedó registrado/confirmado/reservado/anotado" (o similar) si no llamaste a la tool y recibiste ok en ESTE mismo turno.
- Cuando el cliente confirma el resumen ("sí", "dale", "correcto"), tu SIGUIENTE acción es llamar a la tool que registra — NO respondas el texto de confirmación antes de haberla llamado y recibido ok.

RESERVAS
- Las reservas comunes son para grupos chicos que entran en una mesa. Para reservar necesitás fecha, hora y cantidad de personas (y el nombre). Si falta algo, pedilo.
- Resolvé fechas relativas ("mañana", "el sábado", "hoy") según la fecha de hoy.
- Si el cliente pregunta si hay lugar, usá consultar_disponibilidad. Para CONFIRMAR la reserva, llamá SÍ O SÍ a crear_reserva (con fecha, hora, personas y nombre): nunca digas que quedó reservada sin haberla llamado y recibido ok.
- Recién cuando crear_reserva devuelva ok, avisale que la reserva quedó pendiente de confirmación del local.
- IMPORTANTE: si es un grupo grande (8 o más personas) o mencionan un festejo/celebración/reunión (cumpleaños, corporativo, aniversario, etc.), NO es una reserva común y NO le digas que llame al local: pasá al flujo de EVENTOS (abajo) y tomale los datos.

CARTA
- Si piden ver la carta, el menú completo o "la carta en PDF", usá enviar_carta (les manda el PDF) y avisales con una frase corta.
- Para un precio o plato puntual NO mandes el PDF: respondé directo desde el menú.

EVENTOS (corporativos, privados y sociales)
- El local hace eventos: corporativos (desayunos de negocios, presentaciones, workshops, team building, networking), privados y sociales (cumpleaños, casamientos, aniversarios, bautismos, despedidas). Un grupo grande (8+ personas) también se maneja como evento.
- Cuando detectes un evento, hacé el formulario: tomá los datos conversando y de a uno (no todos de golpe), preguntá qué tipo de evento es, nombre de quien organiza (y empresa si es corporativo), fecha/horario estimado, cantidad aproximada de personas, y requerimientos (catering, proyector/sonido, disposición de mesas, presupuesto). Nunca cierres con "llamá al local": la idea es tomarle los datos para que el equipo lo contacte.
- SI ES UN EVENTO CORPORATIVO: pedile además un dato de contacto (teléfono o email) y EN QUÉ HORARIO prefiere que lo llamen para coordinar, y explicale que el equipo de eventos lo va a contactar en ese horario para explicarle cómo son los pasos.
- A MEDIDA que el cliente te da datos del evento, guardalos con guardar_dato_evento (uno o varios por vez, mandá solo los que tengas). Esa tool te devuelve qué falta, y arriba vas a ver un bloque "EVENTO EN CURSO" con lo ya tomado: fijate ahí y pedí SOLO lo que falta.
- NUNCA vuelvas a pedir un dato que la persona ya te dio: mirá el bloque "EVENTO EN CURSO". Si el cliente te corrige ("ya te dije"), NO insistas con esa pregunta: buscá el dato en lo que ya escribió, guardalo si hace falta y seguí con el siguiente que falte.
- Si un dato cambió durante la charla (ej. primero dijo una fecha y después otra), tomá el último valor y confirmáselo explícitamente ("Entonces sería el 18 de agosto, ¿correcto?").
- Antes de registrar, cerrá con un resumen de todos los datos en una línea para que confirme.
- Apenas el cliente confirme el resumen ("sí", "dale", "correcto"), tu PRÓXIMA acción DEBE ser llamar a crear_solicitud_evento (si es corporativo, incluí el contacto y el horario_contacto). guardar_dato_evento NO registra: el paso que REGISTRA la solicitud y avisa al equipo es crear_solicitud_evento.
- Recién DESPUÉS de que crear_solicitud_evento te devuelva ok, decile al cliente que quedó registrada y que el equipo se va a contactar. Si no la llamaste, NO digas que quedó registrada.
- UN evento a la vez: si el cliente quiere organizar DOS o más eventos (o dos reservas) juntos, hacelo DE A UNO — completá y registrá el primero con crear_solicitud_evento, y recién después arrancá con el siguiente. Nunca juntes dos eventos en una sola solicitud ni los des por registrados juntos.

OPINIONES
- Si el cliente deja un elogio o una queja, guardalo con registrar_opinion (con el tipo correcto: elogio o queja).
- La tool te devuelve una 'instruccion' de cómo responder: seguila al pie. Si es una QUEJA, mostrá empatía y avisá que se pasa a atención al cliente. Si es un ELOGIO, agradecé e invitá a calificar en Google pasándole el link que te da la tool.

PEDIDOS PARA LLEVAR
- Para hacer un pedido para llevar hay un PORTAL WEB. Cuando alguien quiera pedir (o pregunte si hay una página/link para pedir), mandale SIEMPRE este link: {link_pedidos}
- En el portal ve el menú con precios, arma el pedido, elige la hora de retiro y paga. Decíselo corto y cálido, tipo "Armá tu pedido acá 👉 {link_pedidos}".
- Aclarale SIEMPRE dos cosas del takeaway: el pago es ÚNICAMENTE con Mercado Pago, y el retiro es a partir de 30 minutos desde que hace el pedido.
- NO tomes el pedido ítem por ítem por chat ni digas que no hay página: la forma de pedir es ese link.
- Si pregunta por un producto o precio puntual, respondé desde el menú; pero para pedir, mandá el link.
- Si un cliente te dice que YA PAGÓ o confirma un pedido (ej. "pagué mi pedido Nº X"), agradecele cálidamente, confirmale que queda en preparación para el horario de retiro, y preguntale si quiere sumar algo más o si tiene algún comentario sobre la experiencia.

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
    system = _build_system(telefono)
    historial = cargar_historial(telefono)
    historial.append({'role': 'user', 'content': texto})

    tools_usadas: set[str] = set()
    for _ in range(MAX_ITERACIONES):
        resp = client.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS_RESPUESTA,
            system=system, tools=TOOLS, messages=historial,
        )
        historial.append({'role': 'assistant', 'content': resp.content})

        if resp.stop_reason != 'tool_use':
            final = _extraer_texto(resp.content) or _RESPUESTA_VACIA
            _red_de_seguridad_evento(telefono, final, tools_usadas)
            _persistir(telefono, texto, final)
            return final

        tools_usadas.update(b.name for b in resp.content if getattr(b, 'type', None) == 'tool_use')
        historial.append({'role': 'user', 'content': _correr_tools(resp.content, telefono)})

    _persistir(telefono, texto, _RESPUESTA_TIMEOUT)
    return _RESPUESTA_TIMEOUT


def _red_de_seguridad_evento(telefono: str, final: str, tools_usadas: set[str]) -> None:
    """Si el bot afirma que registró un evento pero NO llamó a crear_solicitud_evento,
    y hay un borrador completo, lo registra igual (a prueba del olvido del modelo)."""
    if 'crear_solicitud_evento' in tools_usadas:
        return
    t = (final or '').lower()
    if not any(k in t for k in ('registrad', 'registró', 'registraron')):
        return
    if not eventos.borrador_completo(telefono):
        return
    res = eventos.crear_solicitud(telefono, {})   # mergea desde el borrador
    if res.get('ok'):
        print(f'[Red de seguridad] Evento auto-registrado para {telefono} (el modelo no llamó la tool).')


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


def _link_pedidos() -> str:
    """Link público del portal de pedidos (/pedir), para que el bot lo comparta."""
    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    return f'{base}/pedir' if base else '/pedir'


def _build_system(telefono: str):
    """Personalidad fija + datos del local leídos de la DB. Si hay un evento en
    curso, se suma un bloque aparte (sin cache) con lo ya capturado."""
    persona = SYSTEM_PERSONA.format(
        nombre_local=get_config('nombre_local', 'SELQUET'),
        fecha_hoy=date.today().isoformat(),
        link_pedidos=_link_pedidos(),
    )
    partes = [persona]
    bienvenida = get_config('mensaje_bienvenida', '').strip()
    if bienvenida:
        partes.append('MENSAJE DE BIENVENIDA (usalo para presentarte al saludar y, sobre todo, cuando '
                      'alguien quiere hacer un pedido; adaptalo con naturalidad, no hace falta repetirlo textual):\n'
                      + bienvenida)
    partes.append(build_datos_local())
    # Bloque grande y estable → cacheado. El estado del evento cambia por turno y
    # por teléfono, así que va como bloque propio sin cache para no invalidarlo.
    bloques = [{'type': 'text', 'text': '\n\n'.join(partes), 'cache_control': {'type': 'ephemeral'}}]
    estado_evento = eventos.estado_borrador_texto(telefono)
    if estado_evento:
        bloques.append({'type': 'text', 'text': estado_evento})
    return bloques


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
