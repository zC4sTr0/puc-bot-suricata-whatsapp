"""Configuração externa dos destinos da rodada Suricata.

Este é o módulo canônico da borda de configuração. Ele não contém regras de
planejamento nem entrega; apenas valida e materializa destinos configurados no
ambiente do processo.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime

from ..dominio.horario import BRASILIA


_JID_GRUPO = re.compile(r"[0-9]+(?:-[0-9]+)?@g\.us")


@dataclass(frozen=True)
class Destino:
    """Destino configurado externamente; ``grupo`` preserva o contrato legado."""

    identificador: str
    jid: str | None
    prefixo: str
    janela_brt: str | None = None

    def elegivel(self, agora: datetime) -> bool:
        if self.janela_brt is None:
            return True
        return agora.astimezone(BRASILIA).strftime("%H:%M") == self.janela_brt


def destinos_do_ambiente(env: dict[str, str] | None = None) -> list[Destino]:
    """Lê destinos sem nomes/JIDs no código.

    ``SURICATA_GRUPO_JID`` é o destino legado. Destinos adicionais são um
    JSON opt-in em ``SURICATA_DESTINOS_JSON`` (ou ``SURICATA_DESTINOS``),
    com itens ``{"id": "...", "jid": "..."}`` ou uma janela BRT opcional.
    O identificador só pode formar um segmento de caminho seguro.
    """
    ambiente = os.environ if env is None else env
    jid = ambiente.get("SURICATA_GRUPO_JID") or None
    if jid is not None and _JID_GRUPO.fullmatch(jid) is None:
        raise ValueError("JID de destino inválido")
    bruto = ambiente.get("SURICATA_DESTINOS_JSON") or ambiente.get("SURICATA_DESTINOS")
    # Sem o JID legado, não materialize um destino ``grupo`` nulo quando há
    # destinos adicionais. Isso evita que a entrega tente usar um grupo
    # inexistente antes de processar os destinos válidos.
    destinos = [Destino("grupo", jid, "grupo")] if jid or not bruto else []
    if not bruto:
        return destinos
    try:
        configurados = json.loads(bruto)
    except (TypeError, ValueError) as exc:
        raise ValueError("SURICATA_DESTINOS_JSON inválido") from exc
    if not isinstance(configurados, list):
        raise ValueError("SURICATA_DESTINOS_JSON deve ser uma lista")
    if not configurados and not jid:
        raise ValueError("nenhum destino configurado")
    ids = {"grupo"}
    for item in configurados:
        if not isinstance(item, dict):
            raise ValueError("destino deve ser objeto")
        identificador = item.get("id")
        destino_jid = item.get("jid")
        janela = item.get("janela_brt")
        if (not isinstance(identificador, str) or not identificador or identificador in ids
                or "/" in identificador or "\\" in identificador or identificador in {".", ".."}):
            raise ValueError("identificador de destino inválido")
        if not isinstance(destino_jid, str) or not destino_jid.strip():
            raise ValueError("JID de destino ausente")
        if _JID_GRUPO.fullmatch(destino_jid) is None:
            raise ValueError("JID de destino inválido")
        if janela is not None:
            try:
                datetime.strptime(janela, "%H:%M")
            except (TypeError, ValueError) as exc:
                raise ValueError("janela_brt inválida; use HH:MM") from exc
            if datetime.strptime(janela, "%H:%M").minute % 10:
                raise ValueError("janela_brt incompatível com Scheduler de 10 minutos")
        ids.add(identificador)
        destinos.append(Destino(identificador, destino_jid.strip(), f"destinos/{identificador}", janela))
    return destinos


__all__ = ["Destino", "destinos_do_ambiente"]
