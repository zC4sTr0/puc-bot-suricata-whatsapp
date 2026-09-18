"""Compromisso de memória da rodada: novidade só é consumida quando durável.

Extração estrutural do bloco de memória de ``execucao.executar``.
Transformação pura: muta apenas os dicionários recebidos, sem I/O e sem
relógio próprio; contratos e ordem de efeitos preservados.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from .horario import BRASILIA
from .planejamento import Evento


def comprometer_memoria(memoria_comprometida: dict[str, Any],
                        memoria_planejada: dict[str, Any],
                        eventos: list[Evento],
                        duraveis: set[str],
                        entrega: dict[str, Any],
                        momento: datetime) -> dict[str, Any]:
    """Consolida em ``memoria_comprometida`` apenas eventos duráveis no outbox.

    ACK não é necessário para a durabilidade do evento, mas uma falha
    explícita da ponte (``sessao`` fora de ``None``/``"ok"``) não consome a
    memória: a próxima rodada deve reconstruir a intenção e reenviar.
    """
    for evento in eventos:
        if evento.event_id not in duraveis:
            continue
        if entrega.get("sessao") not in (None, "ok"):
            continue
        if evento.atividade is not None:
            chave = evento.atividade.chave
            item_planejado = memoria_planejada.get("itens", {}).get(chave)
            if item_planejado is not None:
                memoria_comprometida.setdefault("itens", {})[chave] = deepcopy(item_planejado)
            # A marca só é consumida depois de o novo ser registrado.
            memoria_comprometida.get("itens", {}).get(chave, {}).pop("novidade_pendente", None)
            if evento.tipo == "novo":
                local = momento.astimezone(BRASILIA)
                amanha = local.date() + timedelta(days=1)
                if amanha in {d.astimezone(BRASILIA).date()
                              for d in (evento.atividade.fecha, evento.atividade.unlock_at)
                              if d is not None}:
                    memoria_comprometida.setdefault("chegando", {})[chave] = amanha.isoformat()
        elif evento.tipo == "anuncio":
            anuncio_id = evento.event_id.rsplit(":", 1)[-1]
            if anuncio_id in memoria_planejada.get("anuncios", {}):
                memoria_comprometida.setdefault("anuncios", {})[anuncio_id] = memoria_planejada["anuncios"][anuncio_id]
        elif evento.tipo == "aviso_prova":
            data_evento = evento.event_id.rsplit(":", 1)[-1]
            if data_evento in memoria_planejada.get("avisos_prova", {}):
                memoria_comprometida.setdefault("avisos_prova", {})[data_evento] = memoria_planejada["avisos_prova"][data_evento]
        elif evento.tipo == "vespera":
            data_evento = evento.event_id.rsplit(":", 1)[-1]
            if data_evento in memoria_planejada.get("vesperas", {}):
                memoria_comprometida.setdefault("vesperas", {})[data_evento] = memoria_planejada["vesperas"][data_evento]
            for campo in ("chegando", "adiantadas"):
                memoria_comprometida[campo] = deepcopy(memoria_planejada.get(campo, {}))
    return memoria_comprometida


__all__ = ["comprometer_memoria"]
