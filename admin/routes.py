"""Panel de administración de SELQUET (blueprint Flask).

Solapas de configuración: Información · FAQs · Menú · Mesas (lo que el bot lee en
cada consulta). Solapas operativas: Reservas (comunes + corporativas) · Takeaway ·
Opiniones, donde el local gestiona lo que va entrando.
"""
import json
import re

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, session, url_for)

import config_store
import notificaciones_panel
from database import SessionLocal
from models import (CambioPrecio, DestinatarioEvento, Faq, MenuItem, MesaConfig,
                    Opinion, Pedido, Reserva, SolicitudEvento)
from reservas import DIAS
from telefono import normalizar_ar as _normalizar_wa

from . import excel_import
from .auth import (ENDPOINTS_NEUTROS, ENDPOINTS_PUBLICOS, autenticar, es_admin,
                   landing_endpoint, puede_acceder, solapas_permitidas)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.context_processor
def _inject_comunes():
    return {
        'nombre_local': config_store.get_config('nombre_local', 'SELQUET'),
        'bot_activo': config_store.is_bot_activo(),
        'es_admin': es_admin(),
        'solapas': solapas_permitidas(),
        'usuario_actual': session.get('usuario', ''),
    }


@admin_bp.before_request
def _control_acceso():
    """Guarda única para todo el panel: exige sesión y valida el rol contra la
    solapa del endpoint. Evita repetir decoradores en cada ruta."""
    endpoint = (request.endpoint or '').rsplit('.', 1)[-1]
    if endpoint in ENDPOINTS_PUBLICOS:
        return
    if not session.get('usuario'):
        return redirect(url_for('admin.login'))
    if endpoint in ENDPOINTS_NEUTROS:
        return
    if not puede_acceder(session.get('rol', ''), endpoint):
        abort(403)


# ─── Auth ───

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = autenticar(request.form.get('usuario', ''), request.form.get('password', ''))
        if usuario:
            session['usuario'] = usuario.username
            session['rol'] = usuario.rol
            return redirect(url_for(landing_endpoint()))
        flash('Usuario o contraseña incorrectos', 'error')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('rol', None)
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
def home():
    return redirect(url_for(landing_endpoint()))


@admin_bp.route('/bot/toggle', methods=['POST'])
def bot_toggle():
    config_store.set_bot_activo(not config_store.is_bot_activo())
    return redirect(request.referrer or url_for(landing_endpoint()))


# ─── Solapa Información ───

@admin_bp.route('/informacion', methods=['GET', 'POST'])
def informacion():
    if request.method == 'POST':
        config_store.set_config({
            campo['clave']: request.form.get(campo['clave'], '')
            for campo in config_store.CAMPOS_INFO
        })
        flash('Información guardada', 'ok')
        return redirect(url_for('admin.informacion'))

    return render_template('admin/informacion.html', active='informacion',
                           campos=config_store.CAMPOS_INFO, valores=config_store.get_all_config())


# ─── Solapa FAQs ───

@admin_bp.route('/faqs')
def faqs():
    db = SessionLocal()
    try:
        items = db.query(Faq).order_by(Faq.id.desc()).all()
    finally:
        db.close()
    return render_template('admin/faqs.html', active='faqs', faqs=items)


@admin_bp.route('/faqs/nueva', methods=['POST'])
def faq_nueva():
    pregunta = (request.form.get('pregunta') or '').strip()
    respuesta = (request.form.get('respuesta') or '').strip()
    if not pregunta or not respuesta:
        flash('Pregunta y respuesta son obligatorias', 'error')
        return redirect(url_for('admin.faqs'))
    db = SessionLocal()
    try:
        db.add(Faq(pregunta=pregunta, respuesta=respuesta, activo=True))
        db.commit()
        flash('FAQ agregada', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.faqs'))


@admin_bp.route('/faqs/<int:fid>/editar', methods=['POST'])
def faq_editar(fid):
    db = SessionLocal()
    try:
        faq = db.get(Faq, fid)
        if faq:
            faq.pregunta = (request.form.get('pregunta') or faq.pregunta).strip()
            faq.respuesta = (request.form.get('respuesta') or faq.respuesta).strip()
            db.commit()
            flash('FAQ actualizada', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.faqs'))


@admin_bp.route('/faqs/<int:fid>/toggle', methods=['POST'])
def faq_toggle(fid):
    db = SessionLocal()
    try:
        faq = db.get(Faq, fid)
        if faq:
            faq.activo = not faq.activo
            db.commit()
    finally:
        db.close()
    return redirect(url_for('admin.faqs'))


@admin_bp.route('/faqs/<int:fid>/borrar', methods=['POST'])
def faq_borrar(fid):
    db = SessionLocal()
    try:
        faq = db.get(Faq, fid)
        if faq:
            db.delete(faq)
            db.commit()
            flash('FAQ eliminada', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.faqs'))


# ─── Solapa Menú ───

@admin_bp.route('/menu')
def menu():
    db = SessionLocal()
    try:
        items = db.query(MenuItem).order_by(MenuItem.categoria, MenuItem.nombre).all()
    finally:
        db.close()
    return render_template('admin/menu.html', active='menu', items=items)


@admin_bp.route('/menu/nuevo', methods=['POST'])
def menu_nuevo():
    nombre = (request.form.get('nombre') or '').strip()
    precio = excel_import.limpiar_precio(request.form.get('precio'))
    if not nombre or precio is None:
        flash('Nombre y precio válido son obligatorios', 'error')
        return redirect(url_for('admin.menu'))
    db = SessionLocal()
    try:
        db.add(MenuItem(
            nombre=nombre,
            categoria=(request.form.get('categoria') or 'General').strip(),
            precio=precio,
            disponible=True,
        ))
        db.commit()
        flash('Producto agregado', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.menu'))


@admin_bp.route('/menu/guardar', methods=['POST'])
def menu_guardar_todo():
    """Guarda de una todos los cambios de la tabla (nombre, categoría, precio,
    disponibilidad). Los campos vienen nombrados por id: nombre_<id>, etc."""
    ids = [int(x) for x in (request.form.get('ids') or '').split(',') if x.strip().isdigit()]
    db = SessionLocal()
    try:
        for item in db.query(MenuItem).filter(MenuItem.id.in_(ids)).all():
            nombre = (request.form.get(f'nombre_{item.id}') or '').strip()
            categoria = (request.form.get(f'categoria_{item.id}') or '').strip()
            precio = excel_import.limpiar_precio(request.form.get(f'precio_{item.id}'))
            if precio is not None and precio != item.precio:
                db.add(CambioPrecio(item_nombre=(nombre or item.nombre),
                                    precio_anterior=item.precio, precio_nuevo=precio))
            if nombre:
                item.nombre = nombre
            if categoria:
                item.categoria = categoria
            if precio is not None:
                item.precio = precio
            item.disponible = f'disp_{item.id}' in request.form   # checkbox: presente = disponible
        db.commit()
        flash(f'{len(ids)} productos guardados', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.menu'))


@admin_bp.route('/menu/<int:mid>/borrar', methods=['POST'])
def menu_borrar(mid):
    db = SessionLocal()
    try:
        item = db.get(MenuItem, mid)
        if item:
            db.delete(item)
            db.commit()
            flash('Producto eliminado', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.menu'))


@admin_bp.route('/menu/plantilla')
def menu_plantilla():
    return Response(
        excel_import.plantilla_csv(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=plantilla_menu.csv'},
    )


@admin_bp.route('/menu/importar', methods=['POST'])
def menu_importar():
    archivo = request.files.get('archivo')
    if not archivo or not archivo.filename:
        flash('Elegí un archivo', 'error')
        return redirect(url_for('admin.menu'))
    try:
        items, meta = excel_import.parse_menu(archivo.filename, archivo.read())
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('admin.menu'))
    if not items:
        flash('No se encontraron productos válidos en el archivo', 'error')
        return redirect(url_for('admin.menu'))

    db = SessionLocal()
    try:
        actuales = db.query(MenuItem).order_by(MenuItem.categoria, MenuItem.nombre).all()
    finally:
        db.close()
    # Previsualización antes de reemplazar: los items van en un campo oculto para
    # confirmarlos sin volver a subir el archivo (evita el límite de la cookie).
    return render_template('admin/menu.html', active='menu', items=actuales,
                           preview_items=items, preview_meta=meta,
                           preview_json=json.dumps(items, ensure_ascii=False))


@admin_bp.route('/menu/importar/confirmar', methods=['POST'])
def menu_importar_confirmar():
    try:
        items = json.loads(request.form.get('items_json') or '[]')
    except json.JSONDecodeError:
        items = []
    if not items:
        flash('No hay productos para importar', 'error')
        return redirect(url_for('admin.menu'))
    db = SessionLocal()
    try:
        viejos = {m.nombre: m.precio for m in db.query(MenuItem).all()}
        for i in items:
            ant = viejos.get(i['nombre'])
            if ant is not None and ant != i['precio']:
                db.add(CambioPrecio(item_nombre=i['nombre'], precio_anterior=ant, precio_nuevo=i['precio']))
        db.query(MenuItem).delete(synchronize_session=False)
        db.add_all([
            MenuItem(nombre=i['nombre'], categoria=i['categoria'],
                     precio=i['precio'], disponible=i['disponible'])
            for i in items
        ])
        db.commit()
        flash(f'Menú reemplazado: {len(items)} productos', 'ok')
    except Exception as e:
        db.rollback()
        flash(f'Error importando: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.menu'))


# ─── Solapa Mesas (config del motor de disponibilidad de reservas) ───

@admin_bp.route('/mesas')
def mesas():
    db = SessionLocal()
    try:
        filas = db.query(MesaConfig).order_by(MesaConfig.dia_semana, MesaConfig.hora_desde).all()
    finally:
        db.close()
    return render_template('admin/mesas.html', active='mesas', filas=filas, dias=DIAS)


@admin_bp.route('/mesas/nueva', methods=['POST'])
def mesa_nueva():
    try:
        fila = MesaConfig(
            dia_semana=int(request.form['dia_semana']),
            hora_desde=request.form['hora_desde'],
            hora_hasta=request.form['hora_hasta'],
            cantidad_mesas=int(request.form.get('cantidad_mesas') or 1),
            capacidad=int(request.form.get('capacidad') or 4),
            duracion_min=int(request.form.get('duracion_min') or 90),
        )
    except (KeyError, ValueError):
        flash('Datos de la franja inválidos', 'error')
        return redirect(url_for('admin.mesas'))
    db = SessionLocal()
    try:
        db.add(fila)
        db.commit()
        flash('Franja agregada', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.mesas'))


@admin_bp.route('/mesas/<int:cid>/editar', methods=['POST'])
def mesa_editar(cid):
    db = SessionLocal()
    try:
        fila = db.get(MesaConfig, cid)
        if fila:
            try:
                fila.dia_semana = int(request.form['dia_semana'])
                fila.hora_desde = request.form['hora_desde']
                fila.hora_hasta = request.form['hora_hasta']
                fila.cantidad_mesas = int(request.form.get('cantidad_mesas') or 1)
                fila.capacidad = int(request.form.get('capacidad') or 4)
                fila.duracion_min = int(request.form.get('duracion_min') or 90)
                db.commit()
                flash('Franja actualizada', 'ok')
            except (KeyError, ValueError):
                flash('Datos de la franja inválidos', 'error')
    finally:
        db.close()
    return redirect(url_for('admin.mesas'))


@admin_bp.route('/mesas/<int:cid>/borrar', methods=['POST'])
def mesa_borrar(cid):
    db = SessionLocal()
    try:
        fila = db.get(MesaConfig, cid)
        if fila:
            db.delete(fila)
            db.commit()
            flash('Franja eliminada', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.mesas'))


# ─── Solapas operativas: Reservas · Takeaway · Opiniones ───

def _rango_dia(fecha_str):
    """(inicio, fin) del día para filtrar por fecha, o (None, None) si no es válida."""
    from datetime import datetime, timedelta
    try:
        d = datetime.strptime(fecha_str, '%Y-%m-%d')
        return d, d + timedelta(days=1)
    except (ValueError, TypeError):
        return None, None


# ── Reservas (sub-solapas: comunes / corporativas) ──

@admin_bp.route('/reservas')
def reservas():
    """Todas las reservas en una sola lista: comunes (mesa) y corporativas
    (solicitudes de eventos) juntas. Las corporativas se diferencian con color y
    muestran si ya fueron contactadas. La config (reporte/destinatarios) va aparte
    (solo admin)."""
    from datetime import datetime
    db = SessionLocal()
    try:
        comunes = db.query(Reserva).filter(Reserva.estado != 'cancelada').all()
        corporativas = db.query(SolicitudEvento).filter(SolicitudEvento.estado != 'cancelada').all()
        destinatarios = db.query(DestinatarioEvento).order_by(DestinatarioEvento.id.desc()).all()
    finally:
        db.close()
    # Lista unificada, más recientes primero (por cuándo entró la reserva).
    items = [('comun', r) for r in comunes] + [('corporativa', s) for s in corporativas]
    items.sort(key=lambda t: t[1].creado_en or datetime.min, reverse=True)
    cfg = config_store.get_all_config()
    return render_template('admin/reservas.html', active='reservas', items=items,
                           destinatarios=destinatarios,
                           jefe_whatsapp=cfg.get('jefe_whatsapp', ''),
                           jefe_email=cfg.get('jefe_email', ''),
                           hora_reporte=cfg.get('hora_reporte', '23:00'))


@admin_bp.route('/reservas/<int:rid>/estado', methods=['POST'])
def reserva_estado(rid):
    nuevo = request.form.get('estado', '')
    if nuevo in ('nueva', 'confirmada', 'cancelada', 'cumplida'):
        db = SessionLocal()
        try:
            reserva = db.get(Reserva, rid)
            if reserva:
                reserva.estado = nuevo
                db.commit()
        finally:
            db.close()
    return redirect(url_for('admin.reservas'))


# ── Takeaway (pedidos) ──

def _pedidos():
    db = SessionLocal()
    try:
        return db.query(Pedido).order_by(Pedido.creado_en.desc()).all()
    finally:
        db.close()


@admin_bp.route('/takeaway')
def takeaway():
    import os
    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    return render_template('admin/takeaway.html', active='takeaway', filas=_pedidos(),
                           link_pedir=(f'{base}/pedir' if base else url_for('pedir.menu', _external=True)),
                           whatsapp_local=config_store.get_config('whatsapp_local', ''))


@admin_bp.route('/takeaway/tabla')
def takeaway_tabla():
    """Fragmento HTML de la tabla de pedidos, para refrescar sin recargar la página."""
    return render_template('admin/_tabla_pedidos.html', filas=_pedidos())


@admin_bp.route('/takeaway/config', methods=['POST'], endpoint='pedidos_config')
def pedidos_config():
    config_store.set_config({'whatsapp_local': _normalizar_wa(request.form.get('whatsapp_local')) or ''})
    flash('WhatsApp del local guardado', 'ok')
    return redirect(url_for('admin.takeaway'))


@admin_bp.route('/takeaway/<int:pid>/estado', methods=['POST'], endpoint='pedido_estado')
def pedido_estado(pid):
    nuevo = request.form.get('estado', '')
    if nuevo not in ('pagado', 'preparado', 'retirado', 'cancelado'):
        return redirect(url_for('admin.takeaway'))
    aprobado = False
    db = SessionLocal()
    try:
        pedido = db.get(Pedido, pid)
        if pedido:
            # "Aprobar" = el local acepta el pedido pagado y lo pasa a preparación.
            aprobado = nuevo == 'preparado' and pedido.estado in ('pagado', 'confirmado')
            pedido.estado = nuevo
            db.commit()
    finally:
        db.close()
    if aprobado:
        _avisar_pedido_aprobado(pid)
    return redirect(url_for('admin.takeaway'))


def _avisar_pedido_aprobado(pid):
    """Al aprobar el pedido, le manda al comprador la confirmación + la comanda por
    WhatsApp (para que la muestre al retirar)."""
    import pedidos
    from whatsapp.providers import get_provider
    pedido = pedidos.obtener(pid)
    if not pedido:
        return
    provider = get_provider()
    hr = pedido.hora_retiro.strftime('%H:%M') if pedido.hora_retiro else 'el horario acordado'
    provider.send_message(
        pedido.wa_id, f'¡Tu pedido fue confirmado por el local! 🎉 Está en preparación. Lo retirás a las {hr}.')
    provider.send_message(pedido.wa_id, pedidos.comanda_texto(pedido))


# ── Opiniones ──

@admin_bp.route('/opiniones')
def opiniones():
    fecha = (request.args.get('fecha') or '').strip()
    ini, fin = _rango_dia(fecha)
    db = SessionLocal()
    try:
        q = db.query(Opinion).order_by(Opinion.creado_en.desc())
        if ini:
            q = q.filter(Opinion.creado_en >= ini, Opinion.creado_en < fin)
        filas = q.all()
    finally:
        db.close()
    return render_template('admin/opiniones.html', active='opiniones', filas=filas, fecha=fecha)


@admin_bp.route('/notificaciones/pendientes')
def notificaciones_pendientes():
    """Notificaciones nuevas para la campana del panel (polling). Se marcan como
    entregadas al leerlas, para no repetirlas."""
    return {'notificaciones': notificaciones_panel.pendientes()}


@admin_bp.route('/pendientes/activos')
def pendientes_activos():
    """Cuántas novedades quedan SIN atender: pedidos pagados a preparar, reservas
    por confirmar y solicitudes corporativas sin contactar. El JS lo consulta por
    polling para hacer sonar y titilar el panel hasta que se resuelvan."""
    db = SessionLocal()
    try:
        pedidos = db.query(Pedido).filter(Pedido.estado.in_(('pagado', 'confirmado'))).count()
        reservas = db.query(Reserva).filter(Reserva.estado == 'nueva').count()
        corporativas = db.query(SolicitudEvento).filter(SolicitudEvento.estado == 'nueva').count()
    finally:
        db.close()
    return {'total': pedidos + reservas + corporativas,
            'pedidos': pedidos, 'reservas': reservas, 'corporativas': corporativas}


# ── Corporativas: configuración (solo admin) + gestión de solicitudes ──

@admin_bp.route('/reservas/corporativas/jefe', methods=['POST'], endpoint='eventos_jefe')
def eventos_jefe():
    numeros = [_normalizar_wa(x) for x in re.split(r'[,\n;]+', request.form.get('jefe_whatsapp') or '')]
    config_store.set_config({
        'jefe_whatsapp': ', '.join(n for n in numeros if n),
        'jefe_email': ', '.join(e.strip() for e in re.split(r'[,\n;]+', request.form.get('jefe_email') or '') if e.strip()),
        'hora_reporte': (request.form.get('hora_reporte') or '23:00').strip(),
    })
    flash('Reporte diario configurado', 'ok')
    return redirect(url_for('admin.reservas', tab='corporativas'))


@admin_bp.route('/reservas/corporativas/reporte/enviar', methods=['POST'], endpoint='eventos_reporte_enviar')
def eventos_reporte_enviar():
    import reporte
    resultado = reporte.enviar()
    if resultado['enviados']:
        flash(f'Reporte enviado ({resultado["enviados"]} destino/s)', 'ok')
    else:
        flash('No hay jefe configurado (WhatsApp o email)', 'error')
    return redirect(url_for('admin.reservas', tab='corporativas'))


@admin_bp.route('/reservas/corporativas/destinatarios/nuevo', methods=['POST'], endpoint='evento_destinatario_nuevo')
def evento_destinatario_nuevo():
    nombre = (request.form.get('nombre') or '').strip()
    email = (request.form.get('email') or '').strip()
    whatsapp = _normalizar_wa(request.form.get('whatsapp'))
    if not nombre or not (email or whatsapp):
        flash('Nombre y al menos un email o WhatsApp son obligatorios', 'error')
        return redirect(url_for('admin.reservas', tab='corporativas'))
    db = SessionLocal()
    try:
        db.add(DestinatarioEvento(nombre=nombre, email=email or None, whatsapp=whatsapp, activo=True))
        db.commit()
        flash('Destinatario agregado', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.reservas', tab='corporativas'))


@admin_bp.route('/reservas/corporativas/destinatarios/<int:did>/toggle', methods=['POST'], endpoint='evento_destinatario_toggle')
def evento_destinatario_toggle(did):
    db = SessionLocal()
    try:
        dest = db.get(DestinatarioEvento, did)
        if dest:
            dest.activo = not dest.activo
            db.commit()
    finally:
        db.close()
    return redirect(url_for('admin.reservas', tab='corporativas'))


@admin_bp.route('/reservas/corporativas/destinatarios/<int:did>/borrar', methods=['POST'], endpoint='evento_destinatario_borrar')
def evento_destinatario_borrar(did):
    db = SessionLocal()
    try:
        dest = db.get(DestinatarioEvento, did)
        if dest:
            db.delete(dest)
            db.commit()
            flash('Destinatario eliminado', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.reservas', tab='corporativas'))


@admin_bp.route('/reservas/corporativas/solicitudes/<int:sid>/estado', methods=['POST'], endpoint='solicitud_estado')
def solicitud_estado(sid):
    nuevo = request.form.get('estado', '')
    if nuevo in ('nueva', 'contactado', 'confirmada', 'cancelada'):
        db = SessionLocal()
        try:
            solicitud = db.get(SolicitudEvento, sid)
            if solicitud:
                solicitud.estado = nuevo
                notas = request.form.get('notas_confirmacion')
                if notas is not None:
                    solicitud.notas_confirmacion = notas.strip()
                db.commit()
                flash('Solicitud actualizada', 'ok')
        finally:
            db.close()
    return redirect(url_for('admin.reservas', tab='corporativas'))
