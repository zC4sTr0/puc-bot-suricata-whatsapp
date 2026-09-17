"""Coleta e decisão da sentinela Suricata em modo sombra.

Este módulo é deliberadamente agnóstico ao transporte: só lê candidatos públicos,
projeta fatos para ``suricata.domain`` e devolve evidência. Não possui memória,
não grava estado pessoal e nunca chama WhatsApp.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .adapter import PublicCollection, PublicResponse
from .domain import DomainError, EventoPublico, normalizar_evento
from .grupo import decidir_grupo as decidir_grupo_publico
from .grupo import renderizar_evento as renderizar_grupo

EXCLUIDAS = frozenset({"289837", "104959"})


@dataclass(frozen=True)
class RespostaColeta:
    status: int | None
    itens: tuple[Mapping[str, Any], ...] = ()
    erro: str | None = None

    @property
    def estado(self) -> str:
        if self.status == 200:
            return "concluida" if self.itens else "vazio_confirmado"
        if self.status in {401, 403}:
            return "acesso_negado"
        if self.status == 404:
            return "ausente"
        if self.status is None:
            return "indisponivel"
        return "erro"


@dataclass
class Coleta:
    planner: RespostaColeta
    ofertas: dict[str, RespostaColeta] = field(default_factory=dict)
    candidatos: list[Mapping[str, Any]] = field(default_factory=list)

    @property
    def estado(self) -> str:
        sucessos = self.planner.status == 200 or any(r.status == 200 for r in self.ofertas.values())
        falhas = self.planner.status != 200 or any(r.status != 200 for r in self.ofertas.values())
        if not sucessos:
            return "indisponivel"
        return "parcial" if falhas else "concluida"


def _campo(resposta: Any, *nomes: str, default: Any = None) -> Any:
    if isinstance(resposta, Mapping):
        for nome in nomes:
            if nome in resposta:
                return resposta[nome]
    for nome in nomes:
        if hasattr(resposta, nome):
            return getattr(resposta, nome)
    return default


def _resposta(raw: Any) -> RespostaColeta:
    status = _campo(raw, "status", "status_code")
    itens = _campo(raw, "items", "itens", default=None)
    if itens is None:
        itens = _campo(raw, "dados", default=[])
    if isinstance(itens, Mapping):
        itens = [itens]
    if not isinstance(itens, (list, tuple)):
        itens = []
    itens_validos = tuple(item for item in itens if isinstance(item, Mapping))
    return RespostaColeta(status if isinstance(status, int) else None, itens_validos,
                          _campo(raw, "erro", "error"))


def _chamar(collector: Any, nomes: tuple[str, ...], argumento: Any = None, *,
            allow_callable: bool = False) -> Any:
    for nome in nomes:
        func = getattr(collector, nome, None)
        if callable(func):
            return func() if argumento is None else func(argumento)
    if allow_callable and callable(collector):
        return collector(argumento) if argumento is not None else collector()
    raise TypeError("dependência de coleta pública não possui operação conhecida")


def _coleta_adapter(adapter: Any, ofertas: tuple[str, ...]) -> Coleta:
    """Converte o contrato ``PublicCanvasSource`` para a sentinela."""
    try:
        resultado = adapter.coletar(ofertas)
    except Exception as exc:
        return Coleta(RespostaColeta(None, erro=type(exc).__name__))
    if not isinstance(resultado, PublicCollection):
        raise TypeError("adapter público retornou uma coleção inválida")
    planner = resultado.planner
    coleta = Coleta(RespostaColeta(planner.status, planner.items, planner.error))
    # A falha do planner é uma barreira: assignments não são evidência
    # utilizável e devem ser ignorados, mesmo que um adapter defeituoso os
    # tenha incluído na coleção retornada.
    if planner.status != 200:
        return coleta
    for oferta, resposta in resultado.assignments.items():
        if not isinstance(resposta, PublicResponse):
            raise TypeError("adapter público retornou resposta inválida")
        coleta.ofertas[str(oferta)] = RespostaColeta(resposta.status, resposta.items, resposta.error)
    vistos: dict[str, Mapping[str, Any]] = {}
    for oferta, resposta in coleta.ofertas.items():
        for item in resposta.itens:
            candidato = dict(item)
            candidato.setdefault("course_id", oferta)
            chave = _chave(candidato)
            if chave and chave not in vistos:
                vistos[chave] = candidato
    coleta.candidatos = list(vistos.values())
    return coleta


def coletar_candidatos_publicos(canvas: Any, ofertas: Iterable[str], *,
                                legacy_collector: bool = False) -> Coleta:
    """Coleta via ``PublicCanvasSource``; o collector legado exige opt-in.

    O caminho padrão aceita apenas ``planner_publico``/``assignments_publicos``
    ou o método ``coletar`` do adapter. Nomes antigos e callables só são
    aceitos quando ``legacy_collector=True``.

    Cada resposta mantém status HTTP explícito para que 403, 404, 500 e
    indisponibilidade não sejam confundidos com uma lista vazia.
    """
    ofertas_normalizadas = tuple(dict.fromkeys(str(o) for o in ofertas))
    if callable(getattr(canvas, "coletar", None)):
        return _coleta_adapter(canvas, tuple(o for o in ofertas_normalizadas if o not in EXCLUIDAS))
    nomes_planner = ("planner_publico", "planner") if legacy_collector else ("planner_publico",)
    nomes_assignments = ("assignments_publicos", "assignments") if legacy_collector else ("assignments_publicos",)
    try:
        planner = _resposta(_chamar(canvas, nomes_planner, allow_callable=legacy_collector))
    except Exception as exc:  # o relatório conserva indisponibilidade sem vazar detalhes
        planner = RespostaColeta(None, erro=type(exc).__name__)
    resultado = Coleta(planner=planner)
    if planner.status != 200:
        return resultado
    vistos: dict[str, Mapping[str, Any]] = {}
    for item in planner.itens:
        chave = _chave(item)
        if chave:
            vistos[chave] = item
    for oferta in ofertas_normalizadas:
        if oferta in EXCLUIDAS:
            continue
        try:
            resposta = _resposta(_chamar(canvas, nomes_assignments, oferta,
                                         allow_callable=legacy_collector))
        except Exception as exc:
            resposta = RespostaColeta(None, erro=type(exc).__name__)
        resultado.ofertas[oferta] = resposta
        for item in resposta.itens:
            item = dict(item)
            item.setdefault("course_id", oferta)
            chave = _chave(item)
            if chave and chave not in vistos:
                vistos[chave] = item
    resultado.candidatos = list(vistos.values())
    return resultado


def _chave(item: Mapping[str, Any]) -> str | None:
    identifier = item.get("event_id") or item.get("assignment_id") or item.get("id")
    if identifier is None:
        return None
    course = item.get("course_id") or item.get("curso_id") or item.get("curso") or "desconhecido"
    return f"{course}:assignment:{identifier}"


def projetar_para_dominio(candidatos: Iterable[Mapping[str, Any]]) -> list[EventoPublico]:
    """Conserva apenas a projeção pública aceita pelo domínio."""
    eventos: list[EventoPublico] = []
    for item in candidatos:
        raw = dict(item)
        identifier = raw.get("event_id") or raw.get("assignment_id") or raw.get("id")
        course = raw.get("curso") or raw.get("context_name") or raw.get("course_id") or ""
        tipo = raw.get("tipo")
        if not tipo:
            tipo = "quiz" if raw.get("quiz_id") is not None or raw.get("eh_quiz") or "quiz" in str(raw.get("name", raw.get("title", ""))).casefold() else "tarefa"
        course_id = raw.get("course_id") or raw.get("curso_id") or course
        public = {
            "event_id": str(raw.get("event_id")) if raw.get("event_id") else f"canvas:pucminas:course:{course_id}:assignment:{identifier}",
            "curso": str(course), "titulo": str(raw.get("titulo") or raw.get("name") or raw.get("title") or "sem título"),
            "tipo": tipo, "unlock_at": raw.get("unlock_at"), "due_at": raw.get("due_at"),
            "lock_at": raw.get("lock_at"), "pontos": raw.get("points_possible", raw.get("pontos")),
            "url": str(raw.get("html_url") or raw.get("url") or ""),
        }
        try:
            eventos.append(normalizar_evento(public))
        except DomainError:
            continue
    return eventos


def executar_rodada_sombra(canvas: Any, ofertas: Iterable[str], momento: Any, *,
                           legacy_collector: bool = False) -> dict[str, Any]:
    """Executa coleta → projeção → decisão e devolve somente relatório."""
    coleta = coletar_candidatos_publicos(canvas, ofertas, legacy_collector=legacy_collector)
    eventos = projetar_para_dominio(coleta.candidatos) if coleta.estado != "indisponivel" else []
    decisoes = [{"event_id": evento.event_id, "decisao": decidir_grupo_publico(_para_grupo(evento), momento)} for evento in eventos]
    avisos = []
    for evento, decisao in zip(eventos, decisoes):
        if decisao["decisao"] != "alertar":
            continue
        aviso = _para_grupo(evento)
        for campo, valor in tuple(aviso.items()):
            if hasattr(valor, "isoformat"):
                aviso[campo] = valor.isoformat()
        aviso["texto"] = renderizar_grupo(aviso, momento)
        avisos.append(aviso)
    falhas = [{"oferta": oferta, "status": resposta.status, "estado": resposta.estado}
              for oferta, resposta in coleta.ofertas.items() if resposta.status != 200]
    return {
        "modo": "sombra", "estado": coleta.estado,
        "coleta": {"planner": {"status": coleta.planner.status, "estado": coleta.planner.estado},
                   "ofertas_consultadas": len(coleta.ofertas), "assignments": sum(len(r.itens) for r in coleta.ofertas.values()),
                   "falhas": falhas},
        "candidatos": len(coleta.candidatos), "projetados": len(eventos),
        "decisoes": decisoes, "avisos": len(avisos), "eventos": avisos,
        "envio_whatsapp": "desabilitado",
    }


def _para_grupo(evento: EventoPublico) -> dict[str, Any]:
    """Passa à política de grupo somente a projeção pública validada."""
    return {
        "event_id": evento.event_id, "curso": evento.curso, "titulo": evento.titulo,
        "tipo": evento.tipo, "unlock_at": evento.unlock_at, "due_at": evento.due_at,
        "lock_at": evento.lock_at, "pontos": evento.pontos, "url": evento.url,
    }


# Vocabulário curto para a futura entrypoint.
rodada_sombra = executar_rodada_sombra
coletar = coletar_candidatos_publicos
projetar = projetar_para_dominio

__all__ = ["Coleta", "RespostaColeta", "EXCLUIDAS", "coletar_candidatos_publicos", "projetar_para_dominio", "executar_rodada_sombra", "rodada_sombra"]
