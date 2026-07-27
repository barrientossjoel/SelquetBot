"""Configuración de base de datos del bot de SELQUET.

Mismo patrón que ocr_web: `DATABASE_URL` manda; si no está, cae a SQLite local.
Para pasar a producción basta apuntar `DATABASE_URL` a un Postgres.
"""
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

# UTF-8 en consola de Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

from models import Base

DATABASE_URL = os.getenv('DATABASE_URL') or "sqlite:///./selquet.db"

if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # el webhook procesa en threads
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Crea las tablas si no existen y, en SQLite, agrega columnas nuevas que
    hayan aparecido en los modelos (auto-migración liviana para desarrollo)."""
    Base.metadata.create_all(bind=engine)
    _agregar_columnas_faltantes()


def _agregar_columnas_faltantes():
    """SQLite: create_all no altera tablas existentes. Agrega las columnas que
    falten (no borra datos ni cambia tipos). En Postgres se usan migraciones."""
    if not DATABASE_URL.startswith('sqlite'):
        return
    insp = inspect(engine)
    existentes = {t: {c['name'] for c in insp.get_columns(t)} for t in insp.get_table_names()}
    with engine.begin() as conn:
        for tabla in Base.metadata.sorted_tables:
            cols_tabla = existentes.get(tabla.name)
            if not cols_tabla:
                continue
            for col in tabla.columns:
                if col.name not in cols_tabla:
                    tipo = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{tabla.name}" ADD COLUMN "{col.name}" {tipo}'))
                    print(f'[DB] Columna agregada: {tabla.name}.{col.name}')


def test_connection() -> bool:
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        print(f"[DB] Error al probar conexión: {e}")
        return False


if __name__ == "__main__":
    init_db()
    print("OK" if test_connection() else "FALLÓ", "—", DATABASE_URL)
