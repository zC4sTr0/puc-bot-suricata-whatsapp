"""Predicados e autorização do corte das 21h da rodada Suricata.

Extração estrutural de ``execucao.py``; funções puras, sem I/O e sem relógio
próprio. O corte é decisão em runtime: eventos não autorizados expiram, e
estado persistido inválido nunca autoriza envio antecipado.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .horario import BRASILIA
from .planejamento import Evento, _pode_aguardar_07h
from .publico import ABERTURA, Atividade


def corte_21h(agora: datetime) -> bool:
    """Corte absoluto: a partir de 21:00 BRT a rodada não reivindica nem envia."""
    local = agora.astimezone(BRASILIA)
    return (local.hour, local.minute, local.second, local.microsecond) >= (21, 0, 0, 0)


def janela_manha(agora: datetime) -> bool:
    """A exceção só pode ser reivindicada entre 07:30 e 07:30:59 BRT."""
    local = agora.astimezone(BRASILIA)
    return (local.hour, local.minute) == ABERTURA


def autorizacao_corte(evento: Evento, agora: datetime) -> dict[str, Any] | None:
    atividade = evento.atividade
    if not _pode_aguardar_07h(evento, agora):
        return None
    return {
        "chave": atividade.chave,
        "tipo": atividade.tipo,
        "titulo": atividade.titulo,
        "fonte": atividade.fonte,
        "unlock_at": atividade.unlock_at.isoformat(),
        "fecha": atividade.fecha.isoformat(),
        "descoberto_em": agora.isoformat(),
    }


def evento_disponivel(registro: dict[str, Any], agora: datetime) -> bool:
    """Não reivindica novidade antes da janela BRT persistida no outbox."""
    disponivel = registro.get("disponivel_em")
    if not disponivel:
        return True
    try:
        return datetime.fromisoformat(disponivel) <= agora
    except (TypeError, ValueError):
        # Estado persistido inválido nunca autoriza um envio antecipado.
        return False


def autorizados_persistidos(fila: Any, atividades: list[Atividade], agora: datetime) -> set[str]:
    atuais = {a.chave: a for a in atividades}
    autorizados: set[str] = set()
    for registro in fila.outbox.pendentes():
        corte = registro.get("corte_21h")
        if not isinstance(corte, dict):
            continue
        chave = corte.get("chave")
        if not isinstance(chave, str):
            continue
        atividade = atuais.get(chave)
        if atividade is None:
            continue
        try:
            descoberta = datetime.fromisoformat(corte["descoberto_em"])
            esperado = Evento.de_atividade("novo", atividade, agora)
            if (autorizacao_corte(esperado, descoberta) == corte
                    and (janela_manha(agora) or corte_21h(agora))):
                autorizados.add(registro["event_id"])
        except (KeyError, TypeError, ValueError):
            # Estado persistido não é evidência. Corrupção fica sem
            # autorização e será descartada pelo corte, sem abortar a rodada.
            continue
    return autorizados


# Nomes históricos preservados: consumidores importam os predicados privados
# de ``execucao`` e de ``rodada``; mantê-los como aliases idênticos evita
# qualquer mudança de contrato.
_corte_21h = corte_21h
_janela_manha = janela_manha
_autorizacao_corte = autorizacao_corte
_evento_disponivel = evento_disponivel
_autorizados_persistidos = autorizados_persistidos

__all__ = ["corte_21h", "janela_manha", "autorizacao_corte", "evento_disponivel",
           "autorizados_persistidos"]
