"""Modelos SQLAlchemy del bot de SELQUET.

El bot no tiene datos propios: lee todo de estas tablas (config, faqs, menu),
que edita el panel de administración. Las tablas de operación (reservas,
pedidos, opiniones) las llenan los flujos de las fases 3-4; por ahora quedan
como esquema para que la solapa Operación tenga dónde leer.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class WhatsAppConversacion(Base):
    """Historial de la conversación entre el cliente y el chat_engine.
    Scope por `telefono` (clientes anónimos). Cleanup diario de registros > 24h.
    """
    __tablename__ = 'whatsapp_conversaciones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telefono = Column(String(20), nullable=False, index=True)
    role = Column(String(20), nullable=False)   # 'user' | 'assistant'
    content = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.now, index=True)


# ─── Base de conocimiento (lo que el panel edita y el bot lee) ───

class Config(Base):
    """Configuración del local como clave-valor (base de conocimiento).
    Claves definidas en config_store.CAMPOS_INFO + flags (ej. bot_activo).
    """
    __tablename__ = 'config'

    clave = Column(String(50), primary_key=True)
    valor = Column(Text, nullable=False, default='')
    actualizado_en = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Faq(Base):
    """Preguntas/respuestas libres que no entran en los campos fijos."""
    __tablename__ = 'faqs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    pregunta = Column(Text, nullable=False)
    respuesta = Column(Text, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime, default=datetime.now)


class MenuItem(Base):
    """Producto del menú. `precio` en pesos enteros (sin decimales)."""
    __tablename__ = 'menu'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(200), nullable=False)
    categoria = Column(String(100), nullable=False, default='General')
    precio = Column(Integer, nullable=False, default=0)
    disponible = Column(Boolean, default=True, nullable=False)   # interruptor Hay/No hay
    creado_en = Column(DateTime, default=datetime.now)


class MesaConfig(Base):
    """Configuración de mesas por día de semana y franja horaria, para el motor
    de disponibilidad de reservas. `dia_semana`: 0=lunes … 6=domingo (weekday()).
    """
    __tablename__ = 'mesas_config'

    id = Column(Integer, primary_key=True, autoincrement=True)
    dia_semana = Column(Integer, nullable=False)          # 0=lunes … 6=domingo
    hora_desde = Column(String(5), nullable=False)        # 'HH:MM'
    hora_hasta = Column(String(5), nullable=False)        # 'HH:MM' ('00:00' = fin del día)
    cantidad_mesas = Column(Integer, nullable=False, default=1)
    capacidad = Column(Integer, nullable=False, default=4)
    duracion_min = Column(Integer, nullable=False, default=90)
    creado_en = Column(DateTime, default=datetime.now)


# ─── Operación (las llenan los flujos de la fase 3) ───

class Reserva(Base):
    __tablename__ = 'reservas'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wa_id = Column(String(20), nullable=False, index=True)
    nombre = Column(String(120))
    fecha_hora = Column(DateTime, nullable=False)
    personas = Column(Integer, nullable=False, default=1)
    estado = Column(String(20), default='nueva')   # nueva | confirmada | cumplida | cancelada
    creado_en = Column(DateTime, default=datetime.now)


class Pedido(Base):
    """Pedido para llevar, del chat del bot o de la web de pedidos (/pedir).

    Pago con MercadoPago: arranca en 'pendiente_pago' y pasa a 'pagado' (a
    cocinar) cuando el webhook confirma. Pago al retirar: entra 'confirmado'
    (en firme, se cobra en el local)."""
    __tablename__ = 'pedidos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wa_id = Column(String(20), nullable=False, index=True)   # teléfono del cliente
    nombre_cliente = Column(String(120))                     # nombre cargado en la web
    canal = Column(String(20), default='whatsapp')           # whatsapp | web
    items = Column(JSON, nullable=False, default=list)       # [{nombre, cantidad, precio}]
    total = Column(Integer, nullable=False, default=0)
    metodo_pago = Column(String(20), default='mercadopago')  # mercadopago | efectivo (al retirar)
    notas = Column(Text)
    estado = Column(String(20), default='pendiente_pago')    # pendiente_pago | pagado | confirmado | preparado | retirado | cancelado
    hora_retiro = Column(DateTime)
    mp_preference_id = Column(String(80))
    mp_payment_id = Column(String(80))
    creado_en = Column(DateTime, default=datetime.now)


class Opinion(Base):
    __tablename__ = 'opiniones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wa_id = Column(String(20), nullable=False, index=True)
    texto = Column(Text, nullable=False)
    tipo = Column(String(20), default='comentario')   # elogio | queja | comentario
    creado_en = Column(DateTime, default=datetime.now)


# ─── Eventos corporativos / privados / sociales ───

class DestinatarioEvento(Base):
    """Personas del equipo que reciben las solicitudes de eventos, por WhatsApp
    y/o email. Se configuran en el panel (solapa Eventos)."""
    __tablename__ = 'destinatarios_evento'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(120), nullable=False)
    email = Column(String(160))
    whatsapp = Column(String(20))
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime, default=datetime.now)


class BorradorEvento(Base):
    """Borrador de una solicitud de evento en curso: el bot va guardando acá cada
    dato apenas lo captura, para no perderlo si el mensaje se cae de la ventana del
    historial. Un borrador abierto por teléfono; al registrar la solicitud
    (eventos.crear_solicitud) se vuelca a SolicitudEvento y se elimina."""
    __tablename__ = 'borradores_evento'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wa_id = Column(String(20), nullable=False, unique=True, index=True)
    tipo_evento = Column(String(80))
    nombre_contacto = Column(String(120))
    empresa = Column(String(160))
    email_contacto = Column(String(160))
    telefono_contacto = Column(String(40))
    horario_contacto = Column(String(120))
    fecha_estimada = Column(String(80))
    cantidad_personas = Column(Integer)
    detalle = Column(Text)
    actualizado_en = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    creado_en = Column(DateTime, default=datetime.now)


class SolicitudEvento(Base):
    """Consulta de evento que arma el bot conversando con el cliente."""
    __tablename__ = 'solicitudes_evento'

    id = Column(Integer, primary_key=True, autoincrement=True)
    wa_id = Column(String(20), nullable=False, index=True)
    tipo_evento = Column(String(80))            # corporativo | privado | social | (texto libre)
    nombre_contacto = Column(String(120))
    empresa = Column(String(160))
    email_contacto = Column(String(160))
    telefono_contacto = Column(String(40))
    horario_contacto = Column(String(120))      # cuándo puede ser contactado (eventos corporativos)
    fecha_estimada = Column(String(80))         # texto libre ("15 de agosto a la noche")
    cantidad_personas = Column(Integer)
    detalle = Column(Text)                      # requerimientos: catering, AV, layout, etc.
    estado = Column(String(20), default='nueva')        # nueva | contactado | confirmada | cancelada
    notas_confirmacion = Column(Text)           # día/hora, personas y menú acordados al confirmar
    creado_en = Column(DateTime, default=datetime.now)
