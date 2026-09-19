"""Coleta de dados do Canvas para uma rodada da Suricata."""
from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..dominio.publico import Atividade, atividade_de
from ..integracao.canvas import CanvasClient, CanvasResponseKind
from .config import cursos_excluidos_do_ambiente

EXCLUIDAS = cursos_excluidos_do_ambiente({})  # compatibilidade com importadores legados


class ColetaIndisponivel(RuntimeError):
    pass


@dataclass(frozen=True)
class Anuncio:
    id: str
    curso_id: str
    curso: str
    titulo: str
    mensagem: str
    url: str


@dataclass
class Coleta:
    atividades: list[Atividade]
    ofertas: int
    falhas: list[str]
    anuncios: list[Anuncio] | None  # None = rota falhou (não é evidência de ausência)


def coletar(canvas: CanvasClient, agora: datetime,
            *, cursos_excluidos: Collection[str] | None = None) -> Coleta:
    cursos = canvas.courses()
    if cursos.kind is not CanvasResponseKind.OK:
        raise ColetaIndisponivel(f"lista de ofertas: {cursos.kind.value} (HTTP {cursos.status})")
    excluidas = (cursos_excluidos_do_ambiente()
                 if cursos_excluidos is None else frozenset(cursos_excluidos))
    ofertas = {c.id: c.name for c in cursos.items if c.id not in excluidas}
    atividades: list[Atividade] = []
    falhas: list[str] = []
    com_tarefa: list[str] = []
    for curso_id in sorted(ofertas):
        resposta = canvas.assignments(curso_id)
        if resposta.kind is not CanvasResponseKind.OK:
            falhas.append(curso_id)
            continue
        if resposta.items:
            com_tarefa.append(curso_id)  # D20: oferta sem nenhuma tarefa fica fora
        atividades.extend(atividade_de(item, curso_id, ofertas[curso_id]) for item in resposta.items)
    if ofertas and len(falhas) == len(ofertas):
        raise ColetaIndisponivel("nenhuma oferta respondeu 200")
    anuncios: list[Anuncio] | None = []
    if com_tarefa:
        inicio = (agora - timedelta(days=3)).date().isoformat()
        resposta = canvas.announcements([f"course_{c}" for c in com_tarefa], inicio)
        if resposta.kind is CanvasResponseKind.OK:
            for item in resposta.items:
                curso_id = item.context_code.removeprefix("course_")
                if curso_id in com_tarefa:
                    anuncios.append(Anuncio(item.id, curso_id, ofertas[curso_id], item.title, item.message, item.html_url))
        else:
            anuncios = None
            falhas.append("anuncios")
    return Coleta(atividades, len(ofertas), falhas, anuncios)
