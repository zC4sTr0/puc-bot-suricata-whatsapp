"""Agrupamento de envios da rodada: publicações da mesma leva viram uma mensagem.

Extração estrutural de ``execucao.py``; função pura. O ``event_id`` do lote
deriva dos eventos que carrega: o reenvio do mesmo conjunto reusa o mesmo
``message_id`` e o WhatsApp não duplica (F42).
"""
from __future__ import annotations

import hashlib
from typing import Any

from .message_id import message_id
from .publico import texto_lote

MAX_LOTE = 5


def agrupar_envios(claims: list[dict[str, Any]], grupo_jid: str) -> list[dict[str, Any]]:
    """Publicações pendentes da mesma leva viram uma mensagem (até 5 por mensagem)."""
    novos = sorted((c for c in claims if c["event_id"].startswith("grupo:novo:")), key=lambda c: c["event_id"])
    envios = [{**c, "claims": [c]} for c in claims if not c["event_id"].startswith("grupo:novo:")]
    if len(novos) < 2:
        return [{**c, "claims": [c]} for c in novos] + envios
    lotes = []
    for inicio in range(0, len(novos), MAX_LOTE):
        parte = novos[inicio:inicio + MAX_LOTE]
        if len(parte) == 1:
            lotes.append({**parte[0], "claims": parte})
            continue
        ident = "grupo:lote:" + hashlib.sha256("|".join(c["event_id"] for c in parte).encode()).hexdigest()[:16]
        lotes.append({"event_id": ident, "message_id": message_id(grupo_jid, ident),
                      "texto": texto_lote([c["texto"] for c in parte]), "claims": parte})
    return lotes + envios


__all__ = ["MAX_LOTE", "agrupar_envios"]
