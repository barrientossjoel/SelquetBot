"""Formateo compartido (bot y panel)."""


def pesos(n) -> str:
    """8500 -> '$8.500' (separador de miles argentino)."""
    try:
        return '$' + f"{int(n):,}".replace(',', '.')
    except (TypeError, ValueError):
        return str(n)


def duracion_humana(minutos) -> str:
    """180 -> '3 horas'; 30 -> '30 minutos'; 90 -> '1 hora y 30 minutos'."""
    try:
        h, m = divmod(int(minutos), 60)
    except (TypeError, ValueError):
        return str(minutos)
    partes = []
    if h:
        partes.append(f"{h} hora" + ('s' if h != 1 else ''))
    if m:
        partes.append(f"{m} minuto" + ('s' if m != 1 else ''))
    return ' y '.join(partes) or '0 minutos'
