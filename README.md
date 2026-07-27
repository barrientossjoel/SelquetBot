# SELQUET Bot — MVP WhatsApp (sandbox)

Asistente de WhatsApp del restaurante SELQUET. Esta primera etapa es **solo el MVP
mínimo en sandbox** (sección 7 de la guía): recibe un mensaje de texto, arma un prompt
con la personalidad de SELQUET, llama a Claude y responde por WhatsApp, con historial
por usuario.

> ⚠️ **Regla madre:** todo se prueba con el **número de prueba de Meta**. Nada productivo,
> nada con el número real de SELQUET, nada con la base de ~5.800 contactos. Si algo obliga
> a salir del sandbox, **frenar y consultar**.

## Stack

Mismo stack que el bot ya productivo de FacturAI (`ocr_web`), recortado para este MVP:

- **Flask** + Blueprint (webhook).
- **Providers abstraídos** (`whatsapp/providers/`): **Meta** (principal, número de prueba)
  y **Twilio** (fallback), seleccionables con `WHATSAPP_PROVIDER`.
- **SQLAlchemy + SQLite** para el historial (para producción se cambia `DATABASE_URL` a Postgres).
- **Claude** vía SDK `anthropic`. Modelo por defecto: `claude-haiku-4-5` (el más barato y
  el óptimo para FAQ conversacional). Se cambia con `CLAUDE_MODEL` sin tocar código.
- Procesamiento del webhook en **thread daemon** (responde 200 rápido) y **dedup** por id de mensaje.

Fuera del MVP (fases siguientes): reservas, flujo de pedido+pago+retiro con MercadoPago,
aviso al gerente, CVs, encuestas, campañas, deploy productivo.

## Estructura

```
SelquetBot/
├── app.py                    # Flask: registra el webhook, crea las tablas
├── database.py               # engine + SessionLocal (DATABASE_URL, default sqlite)
├── models.py                 # WhatsAppConversacion (historial)
├── whatsapp/
│   ├── routes.py             # GET/POST /webhook/whatsapp
│   ├── providers/            # base.py + meta.py + twilio.py + selector
│   ├── chat_engine.py        # Claude + system prompt de SELQUET (menú de ejemplo)
│   ├── conversaciones.py     # historial: 12 turnos y 30 min, TTL 24h
│   └── message_processor.py  # dedup + thread daemon + orquestación
├── test_local.py             # chat de consola sin Meta ni ngrok
├── requirements.txt
├── .env.example
└── README.md
```

## Puesta en marcha

### 1. Entorno

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # y completar los valores
```

Como mínimo, para probar en consola basta con `ANTHROPIC_API_KEY`.

### 2. Probar la lógica sin WhatsApp (recomendado primero)

```bash
python test_local.py
```

Preguntá: *"¿a qué hora abren?"*, *"¿tienen estacionamiento?"*, *"¿cuánto sale la milanesa?"*.
Si responde con coherencia y tono rioplatense, y mantiene el contexto, **el núcleo está OK**.

### 3. Meta for Developers

1. Crear una **App** *Business* y agregarle el producto **WhatsApp**.
2. Copiar el **token temporal**, el **`PHONE_NUMBER_ID`** y cargar tu celular como destinatario.
3. Poner esos valores en `.env` (`WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`) y elegir
   un `WHATSAPP_VERIFY_TOKEN` inventado por vos.

> El token de prueba de Meta **vence cada 24 h**: se regenera a mano en esta etapa. Un `401`
> al enviar suele ser eso.

### 4. Levantar el server y exponerlo

```bash
python app.py                 # escucha en :8000
ngrok http 8000               # en otra terminal → copiar la URL HTTPS
```

En Meta → *Configuration → Webhook*: poner `https://TU-URL.ngrok.io/webhook/whatsapp`,
el mismo `VERIFY_TOKEN`, y **suscribir el campo `messages`**.

### 5. Demo

Mandá un "hola" desde el celu de prueba. Debe aparecer en los logs y volver la respuesta del bot.

## Verificación rápida por consola (sin celular)

```bash
# GET de verificación (challenge)
curl "http://localhost:8000/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=selquet_prueba_123&hub.challenge=12345"
# → debe devolver 12345

# POST simulando un mensaje entrante de Meta
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"changes":[{"value":{"messages":[{"from":"5491100000000","id":"wamid.TEST1","type":"text","text":{"body":"¿a qué hora abren?"}}]}}]}]}'
# → 200 OK; la respuesta se envía por la Graph API (o se loguea si no hay credenciales)
```

## Checklist "listo para mostrar" (sección 13 de la guía)

- [ ] App creada en Meta + WhatsApp agregado.
- [ ] Número de prueba activo y celu nuestro cargado como destinatario.
- [ ] Webhook GET verificado.
- [ ] ngrok exponiendo el local con HTTPS.
- [ ] Mensaje entrante aparece en los logs.
- [ ] El bot responde vía Claude con el tono de SELQUET (horarios, estacionamiento, precios de ejemplo).
- [ ] La conversación mantiene contexto.
- [ ] Nada productivo, nada con el número o la base real de SELQUET.

## Variables de entorno

Ver `.env.example`. Las principales:

| Variable | Para qué |
|---|---|
| `ANTHROPIC_API_KEY` | Key de Claude (con límite de gasto bajo en esta etapa). |
| `CLAUDE_MODEL` | Modelo (default `claude-haiku-4-5`). |
| `WHATSAPP_PROVIDER` | `meta` (default) o `twilio`. |
| `WHATSAPP_VERIFY_TOKEN` | Token que inventamos para el challenge de Meta. |
| `WHATSAPP_API_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | Credenciales del número de prueba de Meta. |
| `DATABASE_URL` | Default SQLite; para producción, un Postgres. |
