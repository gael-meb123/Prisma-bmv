"""Calendario compartido; años nuevos requieren evidencia oficial y revisión."""
from datetime import date, timedelta

FERIADOS_BMV = {2026: frozenset({
    "2026-01-01", "2026-02-02", "2026-03-16", "2026-04-02", "2026-04-03",
    "2026-05-01", "2026-09-16", "2026-11-02", "2026-11-16", "2026-12-12", "2026-12-25",
})}


def calendario_verificado(anio):
    # Una variable de entorno no acredita un nuevo calendario.
    return anio in FERIADOS_BMV


def es_sesion_bmv(d):
    if not calendario_verificado(d.year):
        raise ValueError("Calendario no validado.")
    return d.weekday() < 5 and d.isoformat() not in FERIADOS_BMV[d.year]


def ultimas_sesiones(corte, n):
    actual = date.fromisoformat(corte)
    if actual.isoformat() != corte or type(n) is not int or not 1 <= n <= 366:
        raise ValueError("Corte o ventana inválidos.")
    if not es_sesion_bmv(actual):
        raise ValueError("El corte no es sesión.")
    resultado = []
    while len(resultado) < n:
        if es_sesion_bmv(actual):
            resultado.append(actual.isoformat())
        actual -= timedelta(days=1)
    return list(reversed(resultado))
