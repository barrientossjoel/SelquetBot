# Prueba de pedidos online — SELQUET

Guía para probar la **web de pedidos para llevar** de punta a punta. Toma ~5 minutos.
No hace falta instalar nada: se prueba desde el celular y una compu.

> ⚠️ Esta prueba **no depende de la lista de números de prueba de Meta**. El botón
> "Enviar por WhatsApp" abre el WhatsApp normal (wa.me), así que podés probar desde
> **cualquier celular**.

---

## Links

| Qué | Dónde |
|---|---|
| **Web de pedidos** (lo que ve el cliente) | https://selquet.digitalimpulso.com/pedir |
| **Panel de administración** | https://selquet.digitalimpulso.com/admin |
| Contraseña del panel | `selquet` |

> El sistema está publicado en internet 24/7 en `selquet.digitalimpulso.com` (servidor propio).
> No depende de ninguna compu prendida.

---

## Paso 1 — Configurar el WhatsApp del local (una sola vez)

1. Entrá al **panel**: https://selquet.digitalimpulso.com/admin
2. Contraseña: `selquet`
3. Andá a la solapa **Operación → Pedidos**
4. En el recuadro **"Pedidos online"**, campo *WhatsApp del local*:
   - Para la prueba, poné **tu propio número de celular** (así el pedido te llega a vos).
   - Formato libre, ej. `11 5619-4427`.
5. Tocá **Guardar**.

En ese mismo recuadro está el **link para compartir** (el de `/pedir`).

---

## Paso 2 — Hacer un pedido como cliente (desde el celular)

1. Abrí en el celular: **https://selquet.digitalimpulso.com/pedir**
2. Sumá productos con el botón **+** (el total se actualiza abajo en vivo).
3. Bajá y completá:
   - **Tu nombre**
   - **Tu teléfono**
   - **Hora de retiro** (opcional)
   - **Aclaraciones** (opcional)
4. En "¿Cómo pagás?" dejá **"Al retirar"**.
5. Tocá **Confirmar pedido**.

---

## Paso 3 — Confirmación y envío por WhatsApp

1. Aparece la pantalla **"¡Pedido registrado!"** con el número **"Pedido Nº X"** y el resumen.
2. Tocá el botón verde **"Enviar mi pedido por WhatsApp"**.
3. Se abre WhatsApp con un mensaje **ya escrito**, tipo:
   ```
   Hola, te paso mi pedido. Espero confirmación | Pedido Nº 12

   2x Roll Philadelphia
   1x Gyoza

   Total: $21.200
   Retiro: 21:00
   Pago: al retirar
   A nombre de: Joel
   https://selquet.digitalimpulso.com/pedir/12
   ```
4. Enviá el mensaje al número del local (el que cargaste en el Paso 1).

---

## Paso 4 — Verificar en el panel

1. Volvé al **panel → Operación → Pedidos**.
2. El pedido tiene que aparecer arriba de todo, marcado con **🌐 web**, en estado **confirmado**,
   con el nombre, el teléfono, los ítems y el total.
3. Probá el circuito del local: tocá **Preparado**, y después **Retirado**.

---

## ✅ Checklist de la prueba

- [ ] La web `/pedir` muestra el menú con **los precios correctos**
- [ ] El total se actualiza al sumar/restar productos
- [ ] No deja confirmar sin nombre, sin teléfono o sin productos
- [ ] Después de confirmar muestra **"Pedido Nº X"** con el resumen correcto
- [ ] El botón de WhatsApp abre el chat con el mensaje precargado bien armado
- [ ] El pedido aparece en el **panel → Operación → Pedidos** (con 🌐 web)
- [ ] Se puede pasar el pedido a **Preparado → Retirado**

---

## Notas

- **Menú vacío**: si `/pedir` no muestra productos, es porque en el panel (solapa **Menú**)
  no hay productos con el interruptor en **"Hay"**. Cargá o activá alguno y recargá la web.
- **Pedido mínimo**: si el local configuró un mínimo (solapa Información) y el pedido no lo
  alcanza, la web avisa y no deja confirmar. Es esperado.
- **Pago con MercadoPago**: en esta prueba solo está habilitado **"Al retirar"**. La opción de
  pagar online con MercadoPago se activa cuando se cargue el token de la cuenta; entonces
  aparece un segundo botón y el pedido queda *pendiente de pago* hasta que se confirme el pago.

---

## Qué reportar si algo falla

Anotá, para cada problema: **en qué paso** pasó, **qué esperabas** que pasara, **qué pasó**,
y si podés una **captura**. Con eso lo resolvemos rápido.
