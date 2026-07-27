# SELQUET · Bot por WhatsApp — Guía Funcional + Arranque MVP

> **Para:** equipo de desarrollo PI.NEXT
> **Contenido:** qué hace el bot (visión completa) + cómo arrancar el MVP mínimo en entorno de prueba
> **Regla madre del arranque:** el MVP se hace SOLO en sandbox. Nada productivo, nada con el número real de SELQUET, nada de la base real de clientes.

---

## 1. Objetivo

Construir el asistente de WhatsApp de SELQUET: un **agente de IA** que conversa en lenguaje natural y **opera el negocio** (consultas, reservas, pedidos con pago y coordinación de retiro).

Esta guía tiene dos partes:
- **Qué hace el bot** (secciones 2 y 3): la visión completa del producto, para que el equipo entienda el objetivo final.
- **Cómo arrancar** (secciones 4 en adelante): el MVP mínimo en entorno de prueba, que es lo único que se construye en esta primera etapa.

---

## 2. Qué HACE el bot (visión completa del producto)

### 2.1 Atención y consultas
- Responde en **lenguaje natural** 24/7, con el tono de SELQUET (no es un menú de botones).
- **Horarios** de apertura y cierre.
- **Info del local**: ubicación, si tiene **estacionamiento**, formas de pago, wifi, y demás preguntas frecuentes.
- **Precios y menú**: el bot se **fija los precios reales** (los consulta de una fuente única de precios, siempre actualizada) y responde cuánto sale cada cosa.

### 2.2 Reservas
- Toma **reservas** (fecha, hora, cantidad de personas), las confirma y manda **recordatorio**.

### 2.3 Pedido + pago + retiro (el flujo central)
Este es el circuito más importante. Paso a paso:

1. El cliente arma el **pedido** por chat.
2. El bot consulta precios y le informa el **total**.
3. El bot le manda un **link de pago de MercadoPago** por el mismo chat.
4. El cliente **paga**.
5. Cuando el **pago se confirma** (vía webhook de MercadoPago), pasan dos cosas en simultáneo:
   - **Al cliente** → aviso: pedido confirmado y pagado, lo puede **retirar en X minutos** (tiempo de preparación).
   - **Al local (gerente/encargado del momento)** → aviso: hay un pedido **ya pagado para preparar**, con el detalle de los ítems y el **horario de retiro**.

> Este flujo conecta venta, cobro y cocina en un solo circuito por WhatsApp. Es el diferencial fuerte frente a cualquier chatbot común.

### 2.4 Otros
- **Recibir CVs / postulaciones laborales** (gente que quiere trabajar en el local deja sus datos/CV). *(Confirmar con Christian si "CVS" se refería a esto.)*
- **Registrar opiniones, quejas y encuestas** de los clientes, para reportería.

---

## 3. Qué NO hace el bot

- ❌ **No factura AFIP/ARCA.** El cobro es con MercadoPago; la facturación es otro sistema aparte.
- ❌ **No reemplaza a la cocina ni al salón.** Coordina y avisa, pero cocinan y atienden personas.
- ❌ **No manda campañas masivas sin opt-in.** Solo se le escribe a quien dio permiso.
- ❌ **No decide precios ni menú por su cuenta.** Los toma de la fuente de precios que carga el local.
- ❌ **No maneja plata directamente.** El dinero pasa por MercadoPago; el bot solo genera el link y escucha la confirmación.

---

## 4. Reglas de ESTA etapa (arranque en sandbox)

De todo lo anterior, en la primera etapa **NO se construye todo**. Se prepara el ambiente y se arma un MVP mínimo en prueba.

**SÍ en esta etapa:**
- Usar el **número de prueba** que da Meta (gratis, sin verificar negocio).
- Backend en **local** (o droplet chico de prueba).
- Exponer el webhook con **ngrok**.
- Probar con **1 o 2 celulares nuestros** cargados como destinatarios.
- Historial simple (SQLite o memoria). Postgres puede esperar.

**NO en esta etapa (todavía):**
- ❌ NO verificar el Business Manager de SELQUET.
- ❌ NO usar el número real de SELQUET ni pasarlo a un celular productivo.
- ❌ NO cargar la base de ~5.800 contactos.
- ❌ NO conectar MercadoPago real ni cobros reales.
- ❌ NO poner nada en producción.

> Si algo obliga a salir del sandbox, **frenar y consultar**. No avanzar por las suyas.

---

## 5. Qué preparar (cuentas y herramientas)

1. **Cuenta en Meta for Developers** — gratis. Crear una **App** *Business* y agregarle el producto **WhatsApp** (habilita el número de prueba).
2. **API Key de Anthropic** — la generamos nosotros con **límite de gasto bajo** (ej. USD 5) y se las pasamos.
3. **Python 3.11+** con entorno virtual (`venv`).
4. **ngrok** — cuenta free. Da una URL HTTPS pública al webhook local sin deployar.
5. **Repo privado nuevo** (nada mezclado con producción).
6. *(Opcional)* **droplet chico de DigitalOcean** ($6/mes, lo pagamos nosotros) si prefieren no trabajar en local.

---

## 6. El número de prueba de Meta (clave del arranque)

Al agregar WhatsApp a la app, Meta da automáticamente:
- Un **número de prueba** (lo provee Meta; no es el nuestro ni el de SELQUET).
- Un **token temporal** (dura 24hs, se regenera).
- Un **`PHONE_NUMBER_ID`** de ese número.

Ese número de prueba **no requiere** verificar el negocio, es **gratis** y puede mandar a **hasta 5 números** que se carguen como destinatarios. Cargar ahí el/los celu(es) nuestro(s): ese es el "celular X" para probar. **El número real de SELQUET no entra en esta etapa.**

---

## 7. Alcance del MVP mínimo (lo único a construir ahora)

Que funcione esto y nada más:

1. El webhook **recibe** un mensaje de texto.
2. Se arma un prompt con la **personalidad de SELQUET** (que es un restaurante, horarios, estacionamiento, tono rioplatense).
3. Se llama a **Claude Haiku 4.5** y se obtiene la respuesta.
4. Se **responde** por WhatsApp.
5. **Historial mínimo** por usuario (para dar contexto).

Si el bot contesta con coherencia a "¿a qué hora abren?", "¿tienen estacionamiento?" o "¿cuánto sale tal plato?" (respondiendo desde el prompt, con precios de ejemplo cargados a mano), **la etapa está cumplida**.

**Fuera del MVP (fases siguientes):** reservas reales, flujo de pedido+pago+retiro con MercadoPago, aviso al gerente, recepción de CVs, encuestas, Postgres, campañas y deploy productivo.

---

## 8. Pasos concretos (en orden)

1. **Meta:** crear app → agregar WhatsApp → copiar `token temporal`, `PHONE_NUMBER_ID` y cargar el celu de prueba como destinatario.
2. **Proyecto:** repo, `venv`, instalar `fastapi uvicorn httpx anthropic python-dotenv`.
3. **Webhook GET** (verificación): responder el `hub.challenge` con nuestro `VERIFY_TOKEN`.
4. **ngrok:** `ngrok http 8000` → copiar la URL HTTPS.
5. **Meta:** configurar esa URL + el `VERIFY_TOKEN` en *Configuration → Webhook* y suscribir el campo `messages`.
6. **Webhook POST** (recepción): parsear el mensaje y loguearlo. Mandar un "hola" desde el celu → debe aparecer en logs.
7. **Envío:** función que responde por la Graph API. Probar con texto fijo.
8. **Claude:** reemplazar el texto fijo por la llamada a Haiku con el system prompt de SELQUET.
9. **Historial:** guardar y reenviar los últimos N mensajes.
10. **Demo:** chatear desde el celu de prueba y validar coherencia.

---

## 9. Estructura mínima del proyecto

```
selquet-bot-mvp/
├── main.py            # webhook (GET verify + POST receive) y orquestación
├── whatsapp.py        # enviar mensajes por la Graph API
├── brain.py           # llamada a Claude + system prompt
├── store.py           # historial simple (SQLite o dict en memoria)
├── .env               # credenciales de PRUEBA (nunca al repo)
└── requirements.txt
```

---

## 10. Esqueleto de código (MVP, recortado)

`main.py`
```python
from fastapi import FastAPI, Request, Response, Query
import os
from whatsapp import enviar_texto
from brain import responder
from store import guardar, historial

app = FastAPI()
VERIFY_TOKEN = os.environ["VERIFY_TOKEN"]

@app.get("/webhook")
async def verificar(mode: str = Query(alias="hub.mode"),
                    token: str = Query(alias="hub.verify_token"),
                    challenge: str = Query(alias="hub.challenge")):
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)

@app.post("/webhook")
async def recibir(request: Request):
    data = await request.json()
    try:
        value = data["entry"][0]["changes"][0]["value"]
        if "messages" not in value:
            return {"status": "ignored"}
        msg = value["messages"][0]
        wa_id = msg["from"]
        texto = msg.get("text", {}).get("body", "")

        guardar(wa_id, "user", texto)
        respuesta = responder(historial(wa_id))
        guardar(wa_id, "assistant", respuesta)
        await enviar_texto(wa_id, respuesta)
    except Exception as e:
        print(f"[webhook] error: {e}")
    return {"status": "ok"}
```

`brain.py`
```python
import anthropic, os
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM = """Sos el asistente de WhatsApp del restaurante SELQUET.
Hablás en español rioplatense, amable y directo. Respondés consultas
de horarios, ubicación, estacionamiento, formas de pago y precios del
menú. Si no sabés algo, lo decís; no inventás precios ni datos."""

def responder(mensajes: list) -> str:
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        system=SYSTEM,
        messages=mensajes,   # [{"role": "...", "content": "..."}]
    )
    return "".join(b.text for b in resp.content if b.type == "text")
```

`whatsapp.py`
```python
import httpx, os
URL = f"https://graph.facebook.com/v21.0/{os.environ['PHONE_NUMBER_ID']}/messages"

async def enviar_texto(wa_id: str, texto: str):
    async with httpx.AsyncClient() as c:
        await c.post(URL,
            headers={"Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}"},
            json={"messaging_product": "whatsapp", "to": wa_id,
                  "type": "text", "text": {"body": texto}})
```

`store.py` (memoria, lo más simple para el MVP)
```python
_hist = {}
def guardar(wa_id, rol, texto):
    _hist.setdefault(wa_id, []).append({"role": rol, "content": texto})
    _hist[wa_id] = _hist[wa_id][-12:]      # solo últimos 12
def historial(wa_id):
    return _hist.get(wa_id, [])
```

---

## 11. Variables de entorno (todas de PRUEBA)

```env
VERIFY_TOKEN=selquet_prueba_123     # lo inventamos nosotros
WHATSAPP_TOKEN=                     # token temporal del número de prueba de Meta
PHONE_NUMBER_ID=                    # phone number id del número de prueba
ANTHROPIC_API_KEY=                  # key con límite de gasto bajo
```

> El token de prueba de Meta vence cada 24hs; en esta etapa se regenera a mano. El token permanente se genera recién en la fase productiva.

---

## 12. Roadmap (después del MVP, en orden)

1. **Reservas** reales + confirmación/recordatorio.
2. **Fuente de precios/menú** única y consultable por el bot.
3. **Flujo de pedido + pago + retiro**:
   - link de MercadoPago,
   - webhook de confirmación de pago,
   - aviso al cliente (retiro en X min),
   - aviso al gerente/encargado (preparar pedido pagado + horario de retiro).
4. **Recepción de CVs** y **encuestas/opiniones**.
5. **Base real** + **campañas** (te extrañamos, cumpleaños, NPS) — con opt-in.
6. **Verificación de negocio**, número real de SELQUET y **deploy productivo**.

---

## 13. Checklist "listo para mostrar" (MVP)

- [ ] App creada en Meta + WhatsApp agregado.
- [ ] Número de prueba activo y celu nuestro cargado como destinatario.
- [ ] Webhook GET verificado.
- [ ] ngrok exponiendo el local con HTTPS.
- [ ] Mensaje entrante aparece en los logs.
- [ ] El bot responde un texto fijo.
- [ ] El bot responde vía Claude con el tono de SELQUET (horarios, estacionamiento, precios de ejemplo).
- [ ] La conversación mantiene contexto.
- [ ] Nada productivo, nada con el número o la base real de SELQUET.

---

### Nota para el equipo
Primero **entiendan qué hace el bot** (secciones 2 y 3), pero **construyan solo el MVP mínimo** (sección 7) en el número de prueba. El flujo de pago, el aviso al gerente y el resto son fases posteriores. Cualquier cosa que los obligue a salir del sandbox, consulten antes.
