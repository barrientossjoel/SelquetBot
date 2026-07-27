"""Envío de emails por SMTP (env-driven).

Si no está configurado el SMTP, no rompe: loguea y devuelve False (igual que
MercadoPago sin token). Config por env: SMTP_HOST, SMTP_PORT (default 587),
SMTP_USER, SMTP_PASS, SMTP_FROM (default = SMTP_USER).
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> bool:
    host = os.getenv('SMTP_HOST', '')
    user = os.getenv('SMTP_USER', '')
    password = os.getenv('SMTP_PASS', '')
    if not (host and user and password and destinatario):
        print(f"[Email] (SMTP sin configurar) → {destinatario}: {asunto}")
        return False

    msg = EmailMessage()
    msg['From'] = os.getenv('SMTP_FROM', user)
    msg['To'] = destinatario
    msg['Subject'] = asunto
    msg.set_content(cuerpo)

    try:
        with smtplib.SMTP(host, int(os.getenv('SMTP_PORT', '587')), timeout=20) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[Email] Error enviando a {destinatario}: {e}")
        return False
