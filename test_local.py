"""Simulador de chat por consola — valida tono y coherencia SIN Meta ni ngrok.

Usa el mismo chat_engine e historial (SQLite) que el webhook real.
Requiere ANTHROPIC_API_KEY en el .env.

    python test_local.py
"""
from dotenv import load_dotenv

load_dotenv()

from database import init_db
from whatsapp import chat_engine
from whatsapp.conversaciones import reset_conversacion

TELEFONO_PRUEBA = 'consola-test'


def main():
    init_db()
    print("=== SELQUET Bot — chat de prueba local ===")
    print("Escribí tu mensaje. Comandos: /reset (limpia el historial), /salir\n")
    while True:
        try:
            texto = input("Vos> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not texto:
            continue
        if texto == '/salir':
            break
        if texto == '/reset':
            reset_conversacion(TELEFONO_PRUEBA)
            print("(historial borrado)\n")
            continue
        respuesta = chat_engine.responder(TELEFONO_PRUEBA, texto)
        print(f"SELQUET> {respuesta}\n")


if __name__ == '__main__':
    main()
