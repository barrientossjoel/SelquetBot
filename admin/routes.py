"""Panel de administración de SELQUET (blueprint Flask).

Cuatro solapas: Información · FAQs · Menú · Operación. Todo lo que se edita acá
es lo que el bot lee en cada consulta (config, faqs, menu). Operación es de solo
lectura y por ahora arranca vacía (la llenan las fases 3-4).
"""
import json
import re

from flask import (Blueprint, Response, flash, redirect, render_template,
                   request, session, url_for)

import config_store
import notificaciones_panel
from database import SessionLocal
from models import (CambioPrecio, DestinatarioEvento, Faq, MenuItem, MesaConfig,
                    Opinion, Pedido, Reserva, SolicitudEvento)
from reservas import DIAS
from telefono import normalizar_ar as _normalizar_wa

from . import excel_import
from .auth import login_required, password_ok

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.context_processor
def _inject_comunes():
    return {
        'nombre_local': config_store.get_config('nombre_local', 'SELQUET'),
        'bot_activo': config_store.is_bot_activo(),
    }


# ─── Auth ───

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if password_ok(request.form.get('password', '')):
            session['admin'] = True
            return redirect(url_for('admin.informacion'))
        flash('Contraseña incorrecta', 'error')
    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@login_required
def home():
    return redirect(url_for('admin.informacion'))


@admin_bp.route('/bot/toggle', methods=['POST'])
@login_required
def bot_toggle():
    config_store.set_bot_activo(not config_store.is_bot_activo())
    return redirect(request.referrer or url_for('admin.informacion'))


# ─── Solapa Información ───

@admin_bp.route('/informacion', methods=['GET', 'POST'])
@login_required
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
@login_required
def faqs():
    db = SessionLocal()
    try:
        items = db.query(Faq).order_by(Faq.id.desc()).all()
    finally:
        db.close()
    return render_template('admin/faqs.html', active='faqs', faqs=items)


@admin_bp.route('/faqs/nueva', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def menu():
    db = SessionLocal()
    try:
        items = db.query(MenuItem).order_by(MenuItem.categoria, MenuItem.nombre).all()
    finally:
        db.close()
    return render_template('admin/menu.html', active='menu', items=items)


@admin_bp.route('/menu/nuevo', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
def menu_plantilla():
    return Response(
        excel_import.plantilla_csv(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=plantilla_menu.csv'},
    )


@admin_bp.route('/menu/importar', methods=['POST'])
@login_required
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
@login_required
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
@login_required
def mesas():
    db = SessionLocal()
    try:
        filas = db.query(MesaConfig).order_by(MesaConfig.dia_semana, MesaConfig.hora_desde).all()
    finally:
        db.close()
    return render_template('admin/mesas.html', active='mesas', filas=filas, dias=DIAS)


@admin_bp.route('/mesas/nueva', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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


# ─── Solapa Operación ───

@admin_bp.route('/operacion')
@login_required
def operacion():
    import os
    from datetime import datetime, timedelta
    vista = request.args.get('vista', 'pedidos')
    fecha = (request.args.get('fecha') or '').strip()
    db = SessionLocal()
    try:
        if vista == 'reservas':
            filas = db.query(Reserva).order_by(Reserva.fecha_hora.desc()).all()
        elif vista == 'opiniones':
            q = db.query(Opinion).order_by(Opinion.creado_en.desc())
            if fecha:
                try:
                    d = datetime.strptime(fecha, '%Y-%m-%d')
                    q = q.filter(Opinion.creado_en >= d, Opinion.creado_en < d + timedelta(days=1))
                except ValueError:
                    pass
            filas = q.all()
        else:
            vista = 'pedidos'
            filas = db.query(Pedido).order_by(Pedido.creado_en.desc()).all()
        filas = list(filas)
    finally:
        db.close()
    base = (os.getenv('PUBLIC_BASE_URL') or os.getenv('MP_BASE_URL') or '').rstrip('/')
    return render_template('admin/operacion.html', active='operacion', vista=vista, filas=filas, fecha=fecha,
                           link_pedir=(f'{base}/pedir' if base else url_for('pedir.menu', _external=True)),
                           whatsapp_local=config_store.get_config('whatsapp_local', ''))


@admin_bp.route('/pedidos/config', methods=['POST'])
@login_required
def pedidos_config():
    config_store.set_config({'whatsapp_local': _normalizar_wa(request.form.get('whatsapp_local')) or ''})
    flash('WhatsApp del local guardado', 'ok')
    return redirect(url_for('admin.operacion', vista='pedidos'))


@admin_bp.route('/notificaciones/pendientes')
@login_required
def notificaciones_pendientes():
    """Notificaciones nuevas para la campana del panel (polling). Se marcan como
    entregadas al leerlas, para no repetirlas."""
    return {'notificaciones': notificaciones_panel.pendientes()}


@admin_bp.route('/reservas/<int:rid>/estado', methods=['POST'])
@login_required
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
    return redirect(url_for('admin.operacion', vista='reservas'))


@admin_bp.route('/pedidos/<int:pid>/estado', methods=['POST'])
@login_required
def pedido_estado(pid):
    nuevo = request.form.get('estado', '')
    if nuevo in ('pagado', 'preparado', 'retirado', 'cancelado'):
        db = SessionLocal()
        try:
            pedido = db.get(Pedido, pid)
            if pedido:
                pedido.estado = nuevo
                db.commit()
        finally:
            db.close()
    return redirect(url_for('admin.operacion', vista='pedidos'))


# ─── Solapa Eventos (destinatarios de notificación + solicitudes recibidas) ───

@admin_bp.route('/eventos')
@login_required
def eventos():
    db = SessionLocal()
    try:
        destinatarios = db.query(DestinatarioEvento).order_by(DestinatarioEvento.id.desc()).all()
        solicitudes = db.query(SolicitudEvento).order_by(SolicitudEvento.creado_en.desc()).all()
    finally:
        db.close()
    cfg = config_store.get_all_config()
    return render_template('admin/eventos.html', active='eventos',
                           destinatarios=destinatarios, solicitudes=solicitudes,
                           jefe_whatsapp=cfg.get('jefe_whatsapp', ''),
                           jefe_email=cfg.get('jefe_email', ''),
                           hora_reporte=cfg.get('hora_reporte', '23:00'))


@admin_bp.route('/eventos/jefe', methods=['POST'])
@login_required
def eventos_jefe():
    numeros = [_normalizar_wa(x) for x in re.split(r'[,\n;]+', request.form.get('jefe_whatsapp') or '')]
    config_store.set_config({
        'jefe_whatsapp': ', '.join(n for n in numeros if n),
        'jefe_email': ', '.join(e.strip() for e in re.split(r'[,\n;]+', request.form.get('jefe_email') or '') if e.strip()),
        'hora_reporte': (request.form.get('hora_reporte') or '23:00').strip(),
    })
    flash('Reporte diario configurado', 'ok')
    return redirect(url_for('admin.eventos'))


@admin_bp.route('/eventos/reporte/enviar', methods=['POST'])
@login_required
def eventos_reporte_enviar():
    import reporte
    resultado = reporte.enviar()
    if resultado['enviados']:
        flash(f'Reporte enviado ({resultado["enviados"]} destino/s)', 'ok')
    else:
        flash('No hay jefe configurado (WhatsApp o email)', 'error')
    return redirect(url_for('admin.eventos'))


@admin_bp.route('/eventos/destinatarios/nuevo', methods=['POST'])
@login_required
def evento_destinatario_nuevo():
    nombre = (request.form.get('nombre') or '').strip()
    email = (request.form.get('email') or '').strip()
    whatsapp = _normalizar_wa(request.form.get('whatsapp'))
    if not nombre or not (email or whatsapp):
        flash('Nombre y al menos un email o WhatsApp son obligatorios', 'error')
        return redirect(url_for('admin.eventos'))
    db = SessionLocal()
    try:
        db.add(DestinatarioEvento(nombre=nombre, email=email or None, whatsapp=whatsapp, activo=True))
        db.commit()
        flash('Destinatario agregado', 'ok')
    finally:
        db.close()
    return redirect(url_for('admin.eventos'))


@admin_bp.route('/eventos/destinatarios/<int:did>/toggle', methods=['POST'])
@login_required
def evento_destinatario_toggle(did):
    db = SessionLocal()
    try:
        dest = db.get(DestinatarioEvento, did)
        if dest:
            dest.activo = not dest.activo
            db.commit()
    finally:
        db.close()
    return redirect(url_for('admin.eventos'))


@admin_bp.route('/eventos/destinatarios/<int:did>/borrar', methods=['POST'])
@login_required
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
    return redirect(url_for('admin.eventos'))


@admin_bp.route('/eventos/solicitudes/<int:sid>/estado', methods=['POST'])
@login_required
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
    return redirect(url_for('admin.eventos'))
