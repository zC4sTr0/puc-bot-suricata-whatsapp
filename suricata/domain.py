"""Domínio público e puro do Suricata.

Este módulo não conhece Canvas, armazenamento, WhatsApp ou o Bot pessoal. A
fronteira aceita somente fatos necessários para anunciar uma atividade; dados
de submissão e estado individual são rejeitados antes de qualquer decisão.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import re
import unicodedata
from collections.abc import Mapping
from typing import Any


MAX_CHARS = 1500
URGENTE = timedelta(hours=48)
# D20: Mentoria e Coordenação.
EXCLUIDAS = frozenset({"289837", "104959"})
PROIBIDOS = frozenset({"submission", "entrega", "atraso", "nota", "situacao"})
PALAVRAS_ANUNCIO = frozenset(
    {"prova", "quiz", "avaliacao", "teste", "simulado", "recuperacao", "reavaliacao"}
)


class DomainError(ValueError):
    """Entrada não permitida ou impossível de normalizar no domínio público."""


def _sem_acento(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value.casefold())
        if unicodedata.category(c) != "Mn"
    )


def _campo_publico(key: object) -> str:
    return _sem_acento(str(key)).replace("-", "_")


def _validar_fronteira(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _campo_publico(key) in PROIBIDOS:
                raise DomainError(f"campo não permitido no domínio público: {key}")
            _validar_fronteira(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validar_fronteira(child)


def _data(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DomainError("data inválida") from exc
    else:
        raise DomainError("data deve ser ISO 8601")
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


@dataclass(frozen=True)
class EventoPublico:
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
    def de_mapping(cls, raw: Mapping[str, Any]) -> "EventoPublico":
        _validar_fronteira(raw)
        if not isinstance(raw, Mapping):
            raise DomainError("evento deve ser um objeto")
        def text(name: str, default: str = "") -> str:
            value = raw.get(name, default)
            if value is None:
                return default
            if not isinstance(value, str):
                raise DomainError(f"{name} deve ser texto")
            return value.strip()
        event_id, curso, titulo = text("event_id", text("id")), text("curso"), text("titulo")
        raw_type = text("tipo")
        if not raw_type:
            raw_type = "quiz" if raw.get("eh_quiz") else "tarefa"
        tipo = _sem_acento(raw_type).replace(" ", "_")
        if not event_id or not titulo:
            raise DomainError("event_id e titulo são obrigatórios")
        pontos = raw.get("pontos")
        if pontos in (None, ""):
            numeric = None
        else:
            try:
                numeric = float(pontos)
            except (TypeError, ValueError) as exc:
                raise DomainError("pontos inválidos") from exc
        return cls(event_id, curso, titulo, tipo, _data(raw.get("unlock_at")),
                   _data(raw.get("due_at")), _data(raw.get("lock_at")), numeric, text("url"))


def normalizar_evento(raw: Mapping[str, Any] | EventoPublico) -> EventoPublico:
    """Valida e normaliza um evento, sem preservar campos privados."""
    if isinstance(raw, EventoPublico):
        return raw
    if not isinstance(raw, Mapping):
        raise DomainError("evento deve ser um objeto")
    return EventoPublico.de_mapping(raw)


def ofertas_elegiveis(contagem_por_oferta: Mapping[str, int]) -> set[str]:
    """Seleciona ofertas não excluídas com ao menos uma tarefa na rodada."""
    return {str(offer) for offer, count in contagem_por_oferta.items()
            if str(offer) not in EXCLUIDAS and isinstance(count, int) and count >= 1}


def decidir_grupo(info: Mapping[str, Any] | EventoPublico, momento: datetime) -> str:
    """Classifica anúncio imediato ou diário, sem olhar entrega individual."""
    evento = normalizar_evento(info)
    agora = _data(momento)
    assert agora is not None
    fechamento = evento.lock_at or evento.due_at
    if fechamento is not None and fechamento <= agora:
        return "ignorar_fechado"
    if evento.tipo == "quiz" or evento.tipo == "avaliacao":
        return "alertar"
    if fechamento is not None and fechamento - agora <= URGENTE:
        return "alertar"
    return "nova_no_diario"


def anuncio_relevante(titulo: str, texto: str) -> bool:
    """Detecta palavras acadêmicas relevantes como palavras inteiras."""
    source = _sem_acento(f"{titulo} {texto}")
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", source) for word in PALAVRAS_ANUNCIO)


_TERMOS_PRIVADOS = re.compile(
    r"(?i)\b(?:submissions?|entregas?|entreg(?:ue|ues|ad[oa]s?)|"
    r"atras(?:o|os|ad[oa]s?)|notas?|situa(?:ção|cao|ções|coes)|perdid[oa]s?)\b"
)

# Remove sequências ANSI/OSC antes dos controles para não deixar formatação oculta.
_ANSI = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-Z\\-_])"
)
_CONTROLES = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _publico(text: str) -> str:
    text = re.sub(r"<[^>]*>", "", html.unescape(text))
    text = _ANSI.sub("", text)
    text = _CONTROLES.sub("", text)
    # Defesa final: valores acadêmicos não podem transformar estado pessoal em anúncio.
    # As flexões são explícitas para não apagar palavras legítimas por prefixo.
    text = _TERMOS_PRIVADOS.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _quando(value: datetime | None, agora: datetime | None) -> str:
    if value is None or agora is None:
        return "já está aberto"
    if value <= agora:
        return "já está aberto"
    total = int((value - agora).total_seconds() // 60)
    return f"em {total} min" if total < 120 else f"em {total // 60} h"


def renderizar_publico(info: Mapping[str, Any] | EventoPublico, momento: datetime | None = None) -> str:
    """Renderiza um evento público determinístico, limitado a 1.500 caracteres."""
    event = normalizar_evento(info)
    now = _data(momento) if momento is not None else None
    tipo = "QUIZ" if event.tipo == "quiz" else "PROVA" if event.tipo == "avaliacao" else "TAREFA"
    abre = _quando(event.unlock_at, now)
    fecha = event.lock_at or event.due_at
    fecha_text = fecha.astimezone(timezone.utc).strftime("%d/%m %H:%M") if fecha else "não informado"
    points = f" · {event.pontos:g} pts" if event.pontos is not None else ""
    lines = [f"🚨 *{tipo} NOVO* — {_publico(event.curso)}", _publico(f"{event.titulo}{points}"),
             f"Abre: {abre}", f"Fecha: {fecha_text}", _publico(event.url)]
    result = "\n".join(line for line in lines if line)
    return result[:MAX_CHARS]


# Nomes explícitos para consumidores que preferem o vocabulário do plano.
Evento = EventoPublico
normalizar = normalizar_evento
renderizar_evento = renderizar_publico
renderizar = renderizar_publico

__all__ = ["DomainError", "EventoPublico", "Evento", "EXCLUIDAS", "normalizar_evento",
           "normalizar", "ofertas_elegiveis", "decidir_grupo", "anuncio_relevante",
           "renderizar_publico", "renderizar_evento", "renderizar"]
