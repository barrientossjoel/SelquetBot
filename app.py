"""App Flask del bot de SELQUET (MVP en sandbox).

Levanta el webhook de WhatsApp + el panel de administración, y crea/siembra
las tablas si no existen.
Correr en local:  python app.py   (escucha en :8000)
Exponer con:      ngrok http 8000
"""
import os

from dotenv import load_dotenv
from flask import Flask, Response, redirect, send_file

load_dotenv()

import carta
from admin.routes import admin_bp
from database import init_db
from formato import pesos
from pagos_webhook import pagos_bp
from pedidos_web import pedir_bp
from seed import seed
from whatsapp.routes import whatsapp_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret')
    app.jinja_env.filters['pesos'] = pesos

    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pagos_bp)
    app.register_blueprint(pedir_bp)

    @app.route('/')
    def home():
        return redirect('/admin')

    @app.route('/carta.pdf')
    def carta_pdf():
        """PDF público (con precios del sistema) para que Meta lo baje al enviarlo."""
        if not carta.existe():
            return 'Carta no disponible', 404
        try:
            data = carta.pdf_bytes()
            return Response(data, mimetype='application/pdf', headers={
                'Content-Disposition': 'inline; filename="Carta SELQUET.pdf"',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
            })
        except Exception as e:
            print(f'[Carta] Error generando PDF con precios, sirvo el original: {e}')
            return send_file(carta.ruta_pdf(), mimetype='application/pdf', download_name='Carta SELQUET.pdf')

    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    init_db()
    seed()
    _programar_reporte_diario()
    return app


def _programar_reporte_diario():
    """Programa el envío del reporte de eventos a la hora configurada (hora_reporte)."""
    import config_store
    import reporte
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        print('[Scheduler] apscheduler no instalado; el reporte diario solo se envía manual.')
        return
    hora = config_store.get_config('hora_reporte', '23:00')
    try:
        h, m = (int(x) for x in hora.split(':'))
    except ValueError:
        h, m = 23, 0
    sched = BackgroundScheduler(daemon=True)
    sched.add_job(reporte.enviar, 'cron', hour=h, minute=m, id='reporte_diario')
    sched.start()
    print(f'[Scheduler] Reporte diario programado a las {h:02d}:{m:02d}')


app = create_app()


if __name__ == '__main__':
    puerto = int(os.getenv('PORT', '8000'))
    app.run(host='0.0.0.0', port=puerto, debug=True, use_reloader=False)
