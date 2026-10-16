# SELQUET Bot

Sistema propio de atención por WhatsApp para el restaurante SELQUET: un motor
conversacional sobre **Claude** que reserva mesas, toma solicitudes de eventos,
gestiona pedidos para llevar con cobro real y mantiene al local al tanto de
todo, con un panel de administración propio. **En producción**, corriendo 24/7.

No es un árbol de botones ("escribí 1 para...") ni un builder de chatbots: es
un backend a medida (Flask + SQLAlchemy) con un loop agéntico de function
calling, pensado para conversar como lo haría una persona del local.

## Funcionalidades

- **Chat conversacional** — responde horarios, ubicación, formas de pago,
  FAQs y precios puntuales leyendo siempre datos en vivo del panel (nunca
  inventa ni tiene nada hardcodeado).
- **Reservas de mesa** — motor de disponibilidad propio por franja horaria y
  capacidad configurada; los grupos grandes se derivan automáticamente a
  eventos.
- **Eventos** (corporativos, privados y sociales) — formulario conversacional
  con estado persistente por teléfono: el bot va guardando cada dato apenas
  lo captura y nunca vuelve a preguntar algo ya dado, aunque la charla se
  corte y retome horas después. Avisa al equipo por WhatsApp y email.
- **Pedidos para llevar** — portal web propio (`/pedir`) con el menú, cálculo
  de total, mínimo y anticipación de retiro configurables, y pago con
  **Mercado Pago** (o "al retirar"). También se puede armar por chat.
- **Carta y comanda en PDF** — la carta real del local con los precios del
  sistema actualizados al vuelo, y una comanda con la marca de SELQUET que se
  manda al cliente al aprobar el pedido.
- **Opiniones** — registra elogios y quejas; una queja dispara una alerta
  inmediata a los jefes (WhatsApp + email).
- **Seguimiento post-pedido** — a las pocas horas de un pedido, el bot
  pregunta cómo le fue al cliente y trata la respuesta como una opinión, no
  como un saludo de alguien nuevo.
- **Reporte diario automático** — resumen de pedidos, reservas, eventos y
  opiniones del día, enviado solo a los responsables del local.
- **Panel de administración** (`/admin`) — información del local, FAQs, menú
  (con importación desde Excel), mesas, gestión de reservas/pedidos/eventos,
  notificaciones en vivo (campana + sonido) y usuarios con roles
  (`admin` / `local`).
- **Anti-duplicados y red de seguridad** — no registra dos veces la misma
  reserva/evento, y si el modelo le dice al cliente "quedó registrado" sin
  haber llamado a la herramienta correspondiente, el sistema lo detecta y lo
  registra igual.

## Stack

- **Flask** (blueprints: `whatsapp`, `admin`, `pagos`, `pedir`) + **SQLAlchemy**
  sobre SQLite (migrable a Postgres con solo cambiar `DATABASE_URL`).
- **Claude** (`anthropic` SDK) como motor conversacional, con function calling
  sobre 7 herramientas de acción (reservar, pedir, registrar evento/opinión,
  etc.). En producción: `claude-sonnet-5` (se probó Haiku primero, pero era
  inconsistente en flujos multi-paso como eventos).
- **Proveedor de WhatsApp abstraído** (`whatsapp/providers/`): **Twilio** en
  producción, **Meta Cloud API** disponible como alternativa —
  seleccionable con `WHATSAPP_PROVIDER`, sin tocar el resto del código.
- **Mercado Pago** (Checkout Pro) para el cobro de pedidos.
- **PyMuPDF** para generar la carta y la comanda en PDF.
- **APScheduler** para el reporte diario y el seguimiento post-pedido.
- Deploy con **Gunicorn** (un solo worker, a propósito, para que el
  scheduler no se dispare duplicado) + **pm2** + **Nginx** sobre un droplet
  propio.

## Estructura

```
SelquetBot/
├── app.py                    # Flask: registra blueprints, init DB, seed y scheduler
├── database.py                # engine + SessionLocal (DATABASE_URL, default SQLite)
├── models.py                  # Tablas: conversaciones, config, menú, reservas, pedidos, eventos...
├── config_store.py             # Config del local (clave-valor) que edita el panel
├── carta.py                    # Carta en PDF con precios del sistema
├── comanda.py                   # Comanda/ticket en PDF con branding SELQUET
├── reservas.py                  # Motor de disponibilidad y alta de reservas
├── eventos.py                   # Borrador + alta de solicitudes de evento, aviso al equipo
├── pedidos.py                   # Armado de pedidos (matching de productos, total, mínimo)
├── pedidos_web.py               # Blueprint del portal /pedir
├── pagos.py / pagos_webhook.py  # Integración Mercado Pago (preferencias + webhook)
├── reporte.py                   # Reporte diario a los responsables
├── seguimiento.py                # "¿Cómo te fue?" post-pedido
├── notificaciones.py / notificaciones_panel.py  # Email y avisos en vivo del panel
├── telefono.py / formato.py     # Utilidades (normalización de teléfono, formato $)
├── whatsapp/
│   ├── routes.py               # GET/POST /webhook/whatsapp
│   ├── providers/               # base.py + meta.py + twilio.py + selector
│   ├── chat_engine.py            # Loop agéntico con Claude + system prompt
│   ├── tools.py                  # Herramientas (function calling) del bot
│   ├── contexto.py                # Arma el bloque de datos del local para el prompt
│   ├── conversaciones.py          # Historial por teléfono (turnos, TTL)
│   └── message_processor.py       # Dedup + thread daemon + orquestación
├── admin/
│   ├── routes.py                 # Todas las rutas del panel (con control de acceso por rol)
│   ├── auth.py                    # Login / sesión
│   └── excel_import.py             # Importación del menú desde Excel
├── templates/ , static/          # Vistas y assets del panel y del portal /pedir
├── test_local.py                  # Chat de consola sin WhatsApp ni ngrok
├── deploy.sh                      # git pull + deps + pm2 restart (en el servidor)
├── requirements.txt
└── .env.example
```

## Puesta en marcha (desarrollo local)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # completar los valores (ver tabla abajo)
```

Con solo `ANTHROPIC_API_KEY` alcanza para probar la lógica de charla en
consola:

```bash
python test_local.py
```

Para levantar el server completo (bot + panel + portal de pedidos):

```bash
python app.py                 # escucha en :8000 (admin en /admin, pedidos en /pedir)
ngrok http 8000                # para exponerlo y probar el webhook de WhatsApp/MP
```

## Variables de entorno

Ver `.env.example`. Las principales:

| Variable | Para qué |
|---|---|
| `ANTHROPIC_API_KEY` / `CLAUDE_MODEL` | Key y modelo de Claude (default `claude-haiku-4-5`; producción usa `claude-sonnet-5`). |
| `WHATSAPP_PROVIDER` | `twilio` (producción) o `meta`. |
| `WHATSAPP_API_TOKEN` / `WHATSAPP_PHONE_NUMBER_ID` | Credenciales de Meta Cloud API (si `WHATSAPP_PROVIDER=meta`). |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_WA_NUMBER` | Credenciales de Twilio (si `WHATSAPP_PROVIDER=twilio`). |
| `PUBLIC_BASE_URL` | URL pública del backend (dominio en producción, ngrok en local). La usan el webhook de MP, los `back_urls` y los links de PDF. |
| `MP_ACCESS_TOKEN` / `MP_BASE_URL` | Credencial de Mercado Pago (`TEST-...` no mueve plata real, `APP_USR-...` sí) y URL pública para sus callbacks. |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | Envío de emails a los destinatarios de eventos. |
| `ADMIN_PASSWORD` / `FLASK_SECRET_KEY` | Acceso al panel `/admin` y firma de sesión. |
| `DATABASE_URL` | Default SQLite; en producción migrable a Postgres. |

## Deploy / producción

El sistema corre en un droplet propio, con Gunicorn (un worker) gestionado
por **pm2** detrás de **Nginx** (HTTPS con Let's Encrypt, renovación
automática). Para redeployar tras subir cambios a GitHub:

```bash
./deploy.sh   # git pull --ff-only + pip install + pm2 restart selquet
```

---

Ver también `SALIDA_A_PRODUCCION.md` (guía de prueba integral y pasos de
publicación) e `INFRAESTRUCTURA.md` (detalle de infraestructura, no
versionado por seguridad).
