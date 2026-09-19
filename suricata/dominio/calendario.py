"""Calendário letivo da Suricata: Páscoa, feriados nacionais e dia de aula.

Extração estrutural de ``publico.py``; funções puras de ``date``, sem relógio
nem I/O. Carnaval e Corpus Christi são ponto facultativo, não feriado.
"""
from __future__ import annotations

from datetime import date, timedelta


def _pascoa(ano: int) -> date:
    """Algoritmo de Meeus/Jones/Butcher (calendário gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 - notação canônica de Meeus
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    return date(ano, mes, (h + l - 7 * m + 114) % 31 + 1)


def feriados_nacionais(ano: int) -> set[date]:
    """Feriados nacionais por lei (Leis 662/1949, 6.802/1980, 10.607/2002, 14.759/2023)."""
    fixos = {(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)}
    return {date(ano, m, d) for m, d in fixos} | {_pascoa(ano) - timedelta(days=2)}  # Sexta-feira Santa


def eh_dia_de_aula(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados_nacionais(d.year)


__all__ = ["feriados_nacionais", "eh_dia_de_aula"]
