"""Autenticación del panel. MVP de un solo local: una contraseña por env var,
sesión en cookie. Suficiente para el sandbox; se reemplaza por usuarios reales
si el producto lo requiere.
"""
import os
from functools import wraps

from flask import redirect, session, url_for


def password_ok(pw: str) -> bool:
    return bool(pw) and pw == os.getenv('ADMIN_PASSWORD', 'selquet')


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin.login'))
        return fn(*args, **kwargs)
    return wrapper
