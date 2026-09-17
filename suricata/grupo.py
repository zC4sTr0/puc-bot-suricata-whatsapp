"""Política pura de audiência pública do grupo Suricata.

Este módulo recebe fatos do Canvas, projeta somente os campos necessários ao
anúncio e devolve texto determinístico. Não acessa rede, relógio, estado ou
qualquer identificador pessoal.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import re
import unicodedata
from typing import Any

MAX_CHARS = 1500
JANELA_ALERTA = timedelta(hours=48)
# D20: Mentoria e Coordenação.
EXCLUIDAS = frozenset({"289837", "104959"})
PALAVRAS_ANUNCIO = frozenset(
    {"prova", "quiz", "avaliacao", "teste", "simulado", "recuperacao", "reavaliacao"}
)
_TERMOS_PRIVADOS = re.compile(
    r"(?i)\b(?:submission\w*|entreg\w*|atras\w*|perdid\w*|notas?|situa(?:ção|cao|ções|coes)\w*|"
    r"token\w*|cookie\w*|jwt|segredo\w*)\b"
)
_TAG = re.compile(r"<[^>]*>")
_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-Z\\-_])")
_CONTROLES = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class GrupoError(ValueError):
    """Fato público inválido."""


def _sem_acento(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value.casefold())
        if unicodedata.category(c) != "Mn"
    )


def _texto(value: Any) -> str:
    """Limpa marcação, controles e termos privados sem executar o conteúdo."""
    text = _TAG.sub("", html.unescape(str(value or "")))
    text = _ANSI.sub("", text)
    text = _CONTROLES.sub("", text)
    text = _TERMOS_PRIVADOS.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _data(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GrupoError("data inválida; use ISO 8601") from exc
    else:
        raise GrupoError("data deve ser ISO 8601")
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _tipo(value: Any, titulo: str) -> str:
    normalized = _sem_acento(str(value or "")).replace(" ", "_")
    if normalized in {"quiz", "avaliacao", "prova"}:
        return "avaliacao" if normalized == "prova" else normalized
    if re.search(r"(?<!\w)prova(?!\w)", _sem_acento(titulo)):
        return "avaliacao"
    return "tarefa"


@dataclass(frozen=True)
class EventoGrupo:
    event_id: str
    curso: str
    titulo: str
    tipo: str
    unlock_at: datetime | None = None
    due_at: datetime | None = None
    lock_at: datetime | None = None
    pontos: float | None = None
    url: str = ""

    @classmethod
    def de_mapping(cls, raw: Mapping[str, Any]) -> "EventoGrupo":
        if not isinstance(raw, Mapping):
            raise GrupoError("evento deve ser um objeto")
        event_id = str(raw.get("event_id", raw.get("id", "")) or "").strip()
        titulo = _texto(raw.get("titulo", raw.get("name", "")))
        if not event_id or not titulo:
            raise GrupoError("event_id e titulo são obrigatórios")
        points = raw.get("pontos", raw.get("points_possible"))
        if points in (None, ""):
            numeric = None
        else:
            try:
                numeric = float(points)
            except (TypeError, ValueError) as exc:
                raise GrupoError("pontos inválidos") from exc
        return cls(
            event_id=event_id,
            curso=_texto(raw.get("curso", raw.get("course", ""))),
            titulo=titulo,
            tipo=_tipo(raw.get("tipo") or ("quiz" if raw.get("eh_quiz") else ""), titulo),
            unlock_at=_data(raw.get("unlock_at")),
            due_at=_data(raw.get("due_at")),
            lock_at=_data(raw.get("lock_at")),
            pontos=numeric,
            url=_texto(raw.get("url", "")),
        )


def _evento(info: Mapping[str, Any] | EventoGrupo) -> EventoGrupo:
    return info if isinstance(info, EventoGrupo) else EventoGrupo.de_mapping(info)


def ofertas_elegiveis(contagem_por_oferta: Mapping[str, int]) -> set[str]:
    """Retorna ofertas públicas não excluídas com ao menos uma atribuição."""
    return {
        str(oferta) for oferta, contagem in contagem_por_oferta.items()
        if str(oferta) not in EXCLUIDAS and isinstance(contagem, int)
        and not isinstance(contagem, bool) and contagem >= 1
    }


def decidir_grupo(info: Mapping[str, Any] | EventoGrupo, momento: datetime) -> str:
    """Classifica o evento como alerta imediato ou item do diário."""
    event = _evento(info)
    agora = _data(momento)
    assert agora is not None
    fechamento = event.lock_at or event.due_at
    if fechamento is not None and fechamento <= agora:
        return "ignorar_fechado"
    if event.tipo in {"quiz", "avaliacao"}:
        return "alertar"
    if fechamento is not None and fechamento - agora <= JANELA_ALERTA:
        return "alertar"
    return "nova_no_diario"


def anuncio_relevante(titulo: str, texto: str) -> bool:
    source = _sem_acento(f"{titulo} {texto}")
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", source) for word in PALAVRAS_ANUNCIO)


def _faltam(value: datetime | None, agora: datetime | None) -> str:
    if value is None or agora is None or value <= agora:
        return "já está aberto"
    minutes = int((value - agora).total_seconds() // 60)
    return f"em {minutes} min" if minutes < 120 else f"em {minutes // 60} h"


def _fechamento(event: EventoGrupo) -> datetime | None:
    return event.lock_at or event.due_at


def _duracao(event: EventoGrupo) -> str:
    if not event.unlock_at or not _fechamento(event):
        return "não informada"
    minutes = int((_fechamento(event) - event.unlock_at).total_seconds() // 60)
    if minutes < 60:
        return f"{max(0, minutes)} min"
    hours, rest = divmod(max(0, minutes), 60)
    return f"{hours} h" if not rest else f"{hours} h {rest} min"


def renderizar_evento(info: Mapping[str, Any] | EventoGrupo, momento: datetime | None = None) -> str:
    """Renderiza um único evento, sempre limitado a 1.500 caracteres."""
    event = _evento(info)
    agora = _data(momento) if momento is not None else None
    fechamento = _fechamento(event)
    if event.tipo == "quiz":
        heading, icon = "QUIZ NOVO", "🚨"
    elif event.tipo == "avaliacao":
        heading, icon = "PROVA NOVA", "📝"
    elif fechamento and agora and fechamento - agora <= JANELA_ALERTA:
        heading, icon = "TAREFA COM PRAZO CURTO", "⏳"
    else:
        heading, icon = "TAREFA NOVA", "📣"
    points = f" · {event.pontos:g} pts" if event.pontos is not None else ""
    close_text = fechamento.strftime("%d/%m %H:%M") if fechamento else "não informado"
    lines = [
        f"{icon} *{heading}* — {_texto(event.curso)}",
        f"{_texto(event.titulo)}{points}",
        f"Abre: {_faltam(event.unlock_at, agora)}",
        f"Fecha: {close_text} — fica aberto {_duracao(event)}",
        "Senha: não verificável",
        _texto(event.url),
    ]
    return "\n".join(line for line in lines if line)[:MAX_CHARS]


def renderizar_dia_grupo(eventos: Sequence[Mapping[str, Any] | EventoGrupo], momento: datetime) -> str:
    """Monta o diário; vazio fora de segunda não cria mensagem."""
    agora = _data(momento)
    assert agora is not None
    normalized = sorted(
        (_evento(item) for item in eventos),
        key=lambda e: (_fechamento(e) or datetime.max.replace(tzinfo=timezone.utc), e.event_id),
    )
    if agora.weekday() == 0 and not normalized:
        fim = agora.date() + timedelta(days=6)
        return f"🗓️ *Semana {agora:%d/%m}–{fim:%d/%m}*\nSuricata 🦦"
    if not normalized:
        return ""
    lines = [f"📅 *Hoje, {agora:%d/%m}* — Suricata 🦦"]
    for event in normalized:
        when = _fechamento(event) or event.unlock_at
        time = when.strftime("%H:%M") if when else "--:--"
        kind = "Quiz" if event.tipo == "quiz" else "Prova" if event.tipo == "avaliacao" else "Tarefa"
        lines.append(f"• {time} {kind}: {_texto(event.titulo)} — {_texto(event.curso)}")
    lines.append("Confira sempre no Canvas: ausência de aviso não prova ausência de tarefa.")
    return "\n".join(lines)[:MAX_CHARS]


# Aliases de vocabulário usados pelos consumidores da camada.
Evento = EventoGrupo
renderizar = renderizar_evento

__all__ = [
    "EXCLUIDAS", "GrupoError", "EventoGrupo", "Evento", "ofertas_elegiveis",
    "decidir_grupo", "anuncio_relevante", "renderizar_evento", "renderizar",
    "renderizar_dia_grupo",
]
