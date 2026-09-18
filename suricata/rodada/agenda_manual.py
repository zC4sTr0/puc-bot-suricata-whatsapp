"""Agenda anotada em aula (nota pessoal do titular) como fonte complementar ao Canvas.

A agenda é uma entrada complementar fornecida pelo operador fora do Git; o
publicador Suricata grava uma cópia em ``agenda/manual.json`` no bucket configurado,
então atualizar datas não exige novo deploy.

Regras (Canvas é a fonte viva):
- item ligado a um assignment presente no Canvas é ignorado aqui;
- item solto só entra se o Canvas não tiver prova/quiz da mesma oferta no mesmo dia;
- item sem data ou sem oferta nunca vira aviso;
- divergência de data não é assunto do grupo (vai para o bot pessoal).
Falha ao ler a agenda nunca derruba a rodada: ela só deixa de complementar.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, time
from typing import Any

from ..dominio.publico import BRASILIA, Atividade, dia, dia_provavel

NOME = "agenda/manual.json"
TIPOS = {"avaliacao", "quiz", "tarefa"}


def carregar(objetos: Any) -> tuple[list[dict[str, Any]], str | None]:
    """Devolve (itens, erro). Ausente = lista vazia sem erro."""
    try:
        obj = objetos.ler(NOME)
    except Exception as exc:  # noqa: BLE001 - agenda é complementar
        return [], f"agenda indisponível: {type(exc).__name__}"
    if obj.dados is None:
        return [], None
    try:
        itens = json.loads(obj.dados.decode("utf-8"))["itens"]
        if not isinstance(itens, list):
            raise ValueError
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        return [], "agenda inválida"
    return [i for i in itens if isinstance(i, dict)], None


def _dia_canvas(a: Atividade) -> date | None:
    provavel = dia_provavel(a)
    if provavel is not None:
        return provavel
    return dia(a.fecha) if a.fecha is not None else None


def complementar(atividades: list[Atividade], manual: list[dict[str, Any]]) -> list[Atividade]:
    """Atividades do caderno que o Canvas ainda não cobre (só as datadas e com oferta)."""
    ids_canvas = {(a.curso_id, a.assignment_id) for a in atividades}
    avaliacoes_por_dia = {(a.curso_id, _dia_canvas(a)) for a in atividades if a.tipo in {"avaliacao", "quiz"}}
    extras: list[Atividade] = []
    for item in manual:
        curso_id, tipo = item.get("curso_id"), item.get("tipo")
        try:
            quando = date.fromisoformat(str(item.get("data")))
        except ValueError:
            continue
        if not curso_id or tipo not in TIPOS or not item.get("titulo"):
            continue
        canvas_id = item.get("canvas_assignment_id")
        if canvas_id and (str(curso_id), str(canvas_id)) in ids_canvas:
            continue
        if tipo in {"avaliacao", "quiz"} and (str(curso_id), quando) in avaliacoes_por_dia:
            continue
        inicio = datetime.combine(quando, time(0, 0), tzinfo=BRASILIA)
        fim = datetime.combine(quando, time(23, 59), tzinfo=BRASILIA)
        pontos = item.get("pontos")
        extras.append(Atividade(
            curso_id=str(curso_id), curso=str(item.get("curso") or curso_id),
            assignment_id=f"caderno:{item.get('id') or item['titulo']}", titulo=str(item["titulo"]), tipo=tipo,
            unlock_at=inicio, due_at=None, lock_at=fim,
            pontos=float(pontos) if (
                isinstance(pontos, (int, float))
                and not isinstance(pontos, bool)
                and pontos >= 0
                and math.isfinite(pontos)
            ) else None,
            url="", fonte="caderno",
        ))
    return extras


__all__ = ["NOME", "carregar", "complementar"]
