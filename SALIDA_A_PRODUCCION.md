# SELQUET Bot — Prueba integral y salida a producción

Guía para **Joel**: probar todo el sistema de punta a punta (bot de WhatsApp +
portal de pedidos + panel), y si está OK, dejarlo **en internet** y **publicar el
número de WhatsApp de SELQUET**.

El documento tiene 4 fases:

1. **Prueba funcional completa** — todas las casuísticas.
2. **Criterios de aceptación** — el checklist que tiene que dar verde.
3. **Subir a producción** — sacar la app de la compu local a internet.
4. **Publicar el WhatsApp de SELQUET** — salir del modo prueba de Meta.

> ✅ **La Fase 3 (deploy) ya está hecha:** el sistema vive en internet en
> `https://selquet.digitalimpulso.com`. Queda un único paso técnico (apuntar el webhook de
> Meta) y la **Fase 4** (publicar el número de SELQUET), que la revisa Meta y puede tardar días.

---

# Estado actual (punto de partida)

| Componente | Estado |
|---|---|
| App (Flask) | **Desplegada en internet 24/7** en un servidor propio (droplet DigitalOcean), gestionada con pm2 |
| URL pública | `https://selquet.digitalimpulso.com` (con HTTPS) |
| WhatsApp | **Modo prueba de Meta** (sandbox): solo responde a números cargados en la lista de prueba. *Falta apuntar el webhook de Meta al dominio nuevo (ver abajo).* |
| MercadoPago | **Activo con token productivo** — la opción "Pagar con MercadoPago" ya aparece. ⚠️ **Los pagos son REALES (cobran de verdad).** Para probar, usar montos chicos. |
| Base de datos | SQLite en el disco del servidor (persistente) |

> El sistema ya vive en internet: no depende de ninguna compu prendida ni de ngrok.

---

# FASE 1 — Prueba funcional completa

## 1.0 · Preparación (una vez)

1. **La app ya está online 24/7** en `https://selquet.digitalimpulso.com` (no hay que prender nada).
2. **Cargar el número de Joel en la lista de prueba de Meta** (para poder chatear con el bot):
   - Entrar a https://developers.facebook.com → app **SelquetBot** → **WhatsApp → Configuración de la API**.
   - En la sección **"Para"** → **Administrar lista de destinatarios** → **Agregar número** → poner el celular de Joel.
   - Meta manda un código por WhatsApp → confirmarlo.
   - Anotar el **número de origen** que muestra esa pantalla (el "De"): es el número **al que Joel le escribe** para hablar con el bot.
3. **Configurar el WhatsApp del local** para los pedidos web:
   - Panel → https://selquet.digitalimpulso.com/admin (contraseña: la que esté en `ADMIN_PASSWORD` del `.env`).
   - **Operación → Pedidos** → cargar *WhatsApp del local* (para la prueba, el celular de Joel) → Guardar.
4. **Verificar que hay menú cargado**: Panel → **Menú** → tiene que haber productos con el interruptor en **"Hay"**.

---

## 1.1 · Bot de WhatsApp — casuísticas

> Joel le escribe **al número del bot** (el "De" del paso anterior). Probar cada fila.
> El bot responde en español rioplatense, cálido y corto.

| # | Qué escribir | Qué tiene que pasar |
|---|---|---|
| 1 | "Hola" | Saluda con el **mensaje de bienvenida** configurado (si se cargó). |
| 2 | "¿A qué hora abren?" | Responde con los **horarios** cargados en el panel (Información). |
| 3 | "¿Dónde quedan? ¿Tienen estacionamiento?" | Da **dirección / cómo llegar / estacionamiento** del panel. |
| 4 | "¿Cómo puedo pagar?" / "¿Tienen wifi?" | Responde con los datos cargados (formas de pago, wifi, etc.). |
| 5 | "Mandame la carta" | Envía el **PDF de la carta** con los **precios del sistema** (los del panel/Excel). |
| 6 | "¿Cuánto sale la milanesa?" (un plato real) | Responde el **precio puntual** del menú, **sin** mandar el PDF. |
| 7 | "Quiero reservar mañana a las 21 para 4 personas, soy Joel" | Chequea **disponibilidad** y crea la **reserva** (queda *pendiente de confirmación*). |
| 8 | "¿Tienen lugar el sábado a las 22?" | Responde según la **disponibilidad** configurada (Mesas). |
| 9 | "Somos 30 para un cumpleaños" | **No** lo trata como reserva común ni dice "llamá al local": pasa a **evento** y pide los datos. |
| 10 | "Quiero hacer un evento corporativo para la empresa" | Toma datos de a uno, pide **contacto + en qué horario llamar**, y registra la **solicitud de evento**. |
| 11 | "Los felicito, comí bárbaro" | Agradece y **registra la opinión** (elogio). |
| 12 | "La pasé mal, tardaron mucho" | Registra la **opinión** (queja) y responde con empatía. |
| 13 | "Quiero pedir 2 empanadas para llevar" (por chat) | Arma el pedido, calcula el **total**, valida el **mínimo** y manda el **link de pago**; aclara que se cocina al pagar. |
| 14 | "Quiero pedir" / "¿Cómo hago un pedido?" | Según cómo se configuró: toma el pedido por chat **o** comparte el link del portal `/pedir`. |

**Verificar en el panel** que caen los resultados:
- Reservas → **Operación → Reservas** (probar **Confirmar** / **Cancelar**).
- Opiniones → **Operación → Opiniones**.
- Eventos → **Eventos**: la solicitud aparece; a los **destinatarios** cargados les llega el aviso (WhatsApp + email); probar marcar **Contactado** / **Confirmar reserva** (con día, hora, personas y menú).
- Pedidos por chat → **Operación → Pedidos**.

---

## 1.2 · Portal de pedidos web (`/pedir`)

> Desde el celular, entrar a **https://selquet.digitalimpulso.com/pedir**.

| # | Caso | Qué tiene que pasar |
|---|---|---|
| 1 | Sumar productos con **+** / **−** | El total se actualiza en vivo. |
| 2 | Confirmar sin nombre / sin teléfono / sin productos | **No deja**: avisa qué falta. |
| 3 | Pedido por debajo del mínimo (si hay mínimo configurado) | Avisa el mínimo y **no deja** confirmar. |
| 4 | Pedido válido, **"Al retirar"** → Confirmar | Muestra **"Pedido Nº X"** con el resumen correcto. |
| 5 | Tocar **"Enviar mi pedido por WhatsApp"** | Abre WhatsApp con el mensaje **precargado** hacia el número del local. |
| 6 | Revisar el panel | El pedido aparece en **Operación → Pedidos** con **🌐 web**, estado **confirmado**. |
| 7 | En el panel, pasar el pedido a **Preparado → Retirado** | Cambia de estado correctamente. |
| 8 | Elegir **MercadoPago** → Confirmar | Aparece el botón **"Pagar ahora con MercadoPago"**; el pedido queda **pendiente de pago**. Al pagar (⚠️ **pago real**, usar monto chico) pasa a **pagado**. |

---

## 1.3 · Panel de administración

| Área | Qué probar |
|---|---|
| **Información** | Editar horarios/dirección/etc. y ver que el bot los usa al toque. |
| **FAQs** | Agregar una pregunta/respuesta y verificar que el bot la contesta. |
| **Menú** | Editar un precio → el bot y la carta PDF muestran el nuevo precio. Probar **importar Excel**. |
| **Mesas** | Cargar franjas horarias y ver que la disponibilidad de reservas las respeta. |
| **Eventos** | Cargar **destinatarios** y **jefes** (varios, separados por coma). Probar **"Enviar reporte ahora"**. |
| **Bot ON/OFF** | Apagar el bot (botón arriba) → deja de responder; prenderlo → vuelve. |

---

# FASE 2 — Criterios de aceptación

Sale a producción **solo si todo esto da verde**:

- [ ] El bot responde info, horarios y precios correctos (los del panel).
- [ ] Manda la carta PDF con los precios actualizados del sistema.
- [ ] Toma reservas y respeta la disponibilidad; los grupos grandes van a eventos.
- [ ] Toma solicitudes de eventos y avisa a los destinatarios; el reporte diario llega a los jefes.
- [ ] Registra opiniones (elogios y quejas).
- [ ] El portal `/pedir` arma pedidos, valida datos y mínimo, y arma el WhatsApp al local.
- [ ] Los pedidos (chat y web) caen en el panel y se pueden gestionar (Preparado → Retirado).
- [ ] El pago con MercadoPago genera link y confirma el pedido al pagar (⚠️ pago real, monto chico).
- [ ] Prender/apagar el bot funciona.

> Anotar cualquier falla con: **paso, qué se esperaba, qué pasó, captura**.

---

# FASE 3 — Subir a producción (deploy) ✅ HECHO

El sistema **ya está desplegado en internet 24/7** en `https://selquet.digitalimpulso.com`.

Cómo quedó armado (para referencia del equipo):
- **Servidor:** droplet DigitalOcean (`157.245.8.219`, Ubuntu). Convive con el proyecto viejo sin pisarlo.
- **Proceso:** gunicorn gestionado con **pm2** (`selquet`), en `127.0.0.1:8000`, persistente (arranca solo si el server reinicia).
- **Web:** nginx hace de puente para `selquet.digitalimpulso.com` con **HTTPS** (Let's Encrypt, renovación automática).
- **Base:** SQLite en el disco del servidor (persistente). *Postgres está disponible en el droplet si más adelante se quiere migrar.*
- **Secretos:** cargados en el `.env` del servidor; `ADMIN_PASSWORD` y `FLASK_SECRET_KEY` nuevos y fuertes.

**Único pendiente para que el bot conteste desde producción:** apuntar el webhook de Meta al dominio nuevo (ver **"Paso final"** abajo). El webhook de MercadoPago ya queda automático (usa `PUBLIC_BASE_URL`).

### Actualizar el código en el futuro
Cuando haya cambios, se vuelve a subir el código al droplet y se reinicia el proceso:
`pm2 restart selquet`. (Ese redeploy lo puedo ejecutar yo.)

---

# Paso final — apuntar el webhook de Meta al dominio nuevo

Para que el bot conteste desde el servidor (y no desde ngrok), hay que actualizar el webhook en Meta:

1. https://developers.facebook.com → app **SelquetBot** → **WhatsApp → Configuración**.
2. En **Webhook**, editar la **URL de devolución de llamada**:
   `https://selquet.digitalimpulso.com/webhook/whatsapp`
3. **Token de verificación:** `selquet_prueba_123`
4. **Verificar y guardar** (Meta valida el token; ya probamos que responde OK).
5. Confirmar que está **suscripto al campo `messages`**.

Desde ese momento, los mensajes de WhatsApp los atiende el servidor de producción.

---

# FASE 4 — Publicar el WhatsApp de SELQUET

**Objetivo:** que el bot atienda al **número real de SELQUET** y le responda a **cualquiera**
(no solo a la lista de prueba).

> Esto se hace en Meta y **depende de una revisión de Meta** que puede tardar. No siempre sale el mismo día.
> Lo tiene que hacer alguien con acceso al **Business Manager de SELQUET**.

### Pasos
1. **Verificación del negocio** (Business Verification) en el Business Manager de SELQUET
   (documentación de la empresa). Sin esto, el número queda con límites de prueba.
2. **Agregar el número productivo** a la WABA de Selquet:
   - Un número de teléfono **real de SELQUET** que **no** esté usado en otra cuenta de WhatsApp
     (ni WhatsApp normal ni Business). Meta lo verifica por **SMS o llamada**.
3. **Nombre para mostrar** (display name) del número → lo **revisa Meta**.
4. **Pasar la app a modo Live** (dejar el modo Desarrollo).
5. **Actualizar en producción**:
   - `WHATSAPP_PHONE_NUMBER_ID` → el del número productivo.
   - `WHATSAPP_API_TOKEN` → ya es el **token permanente** del System User (no vence).
6. **Quitar la dependencia de la lista de prueba**: con la app Live y el número productivo,
   el bot ya responde a cualquier cliente.

### Qué necesita SELQUET tener a mano
- Documentación de la empresa para la verificación.
- El **número de teléfono** que va a usar el bot (libre de otras cuentas de WhatsApp).
- Acceso de administrador al **Business Manager**.

---

# Post-deploy — verificación final en producción (ya con todo publicado)

- [ ] Un cliente **cualquiera** (fuera de la lista de prueba) le escribe al número de SELQUET y el bot responde.
- [ ] El portal `/pedir` abre en el **dominio nuevo** (no ngrok).
- [ ] Un pedido real cae en el panel y el WhatsApp al local funciona.
- [ ] *(Si hay MP)* Un pago real se confirma y el pedido pasa a **pagado**.
- [ ] El reporte diario de eventos llega a los jefes.

---

# Quién hace qué

| Tarea | Quién | ¿Hoy? |
|---|---|---|
| Fase 1 y 2 (probar todo) | Joel | ✅ Sí |
| Cargar número de Joel en lista de prueba | Quien administre la app en Meta | ✅ Sí |
| Fase 3 (deploy a internet) | Ya hecho ✅ | ✅ Listo |
| Apuntar el webhook de Meta al dominio nuevo | Quien administre la app en Meta | ✅ Sí (5 min) |
| Fase 4 (publicar número SELQUET) | Admin del Business Manager de SELQUET | ⏳ Depende de la revisión de Meta |

---

## Notas

- **MercadoPago**: está cargado el **token productivo**, así que los pagos que se hagan son
  **reales** (cobran de verdad). Para la prueba, usar **montos chicos**. La plata entra a la
  cuenta de MercadoPago de SELQUET.
- **Seguridad antes de publicar**: cambiar `ADMIN_PASSWORD` y `FLASK_SECRET_KEY` por valores reales.
- **Datos**: al pasar a producción con PostgreSQL, la base arranca vacía (los datos de prueba de
  SQLite no se migran salvo que se pida expresamente).
