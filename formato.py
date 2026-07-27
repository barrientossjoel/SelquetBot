"""Formateo compartido (bot y panel)."""


def pesos(n) -> str:
    """8500 -> '$8.500' (separador de miles argentino)."""
    try:
        return '$' + f"{int(n):,}".replace(',', '.')
    except (TypeError, ValueError):
        return str(n)
