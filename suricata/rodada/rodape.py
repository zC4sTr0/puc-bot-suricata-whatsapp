"""Rodapé discreto com o link do repositório, anexado a um aviso normal.

Opt-in por ``SURICATA_REPO_URL`` (https). Nunca vira mensagem própria: vai no
fim do último texto de um lote que já seria enviado. O primeiro rodapé sai 7
dias depois do primeiro envio visto; os seguintes esperam mais e, depois do
último intervalo, o rodapé para de vez. O estado fica em
``<destino>/rodape.json`` e só avança com ACK. Qualquer falha de estado
simplesmente omite o rodapé: o aviso nunca depende dele.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any

from ..dominio.publico import BRASILIA

INTERVALOS = (7, 14, 28)  # dias até cada rodapé; depois do último, nunca mais


def _url() -> str | None:
    url = os.environ.get("SURICATA_REPO_URL", "").strip()
    return url if url.startswith("https://") and " " not in url else None


def devido(estado: dict, hoje: date) -> bool:
    mostrados = estado.get("mostrados", 0)
    if mostrados >= len(INTERVALOS):
        return False
    base = date.fromisoformat(estado.get("ultimo") or estado["inicio"])
    return hoje >= base + timedelta(days=INTERVALOS[mostrados])


def anexar(objetos: Any, outbox_nome: str, envios: list[dict], agora: datetime) -> dict | None:
    """Anexa o rodapé ao último envio se devido; devolve o contexto para ``confirmar``."""
    url = _url()
    if not url or not envios or objetos is None:
        return None
    nome = outbox_nome.rsplit("/", 1)[0] + "/rodape.json"
    hoje = agora.astimezone(BRASILIA).date()
    try:
        obj = objetos.ler(nome)
        estado = json.loads(obj.dados) if obj.dados else None
        if not isinstance(estado, dict) or "inicio" not in estado:
            # Primeiro envio visto: só marca o início da contagem.
            objetos.gravar(nome, json.dumps({"inicio": hoje.isoformat()}).encode(), generation=obj.generation)
            return None
        if not devido(estado, hoje):
            return None
    except Exception:  # noqa: BLE001 - rodapé é cortesia; nunca bloqueia o aviso
        return None
    envios[-1] = {**envios[-1], "texto": f"{envios[-1]['texto']}\n\n_A Suricata é código aberto:_ {url}"}
    return {"nome": nome, "generation": obj.generation, "estado": estado,
            "event_id": envios[-1]["event_id"], "hoje": hoje.isoformat()}


def confirmar(objetos: Any, contexto: dict | None, sem_ack: list[str]) -> None:
    """Avança o estado só se o envio que levou o rodapé teve ACK."""
    if not contexto or contexto["event_id"] in sem_ack:
        return
    estado = {**contexto["estado"], "mostrados": contexto["estado"].get("mostrados", 0) + 1,
              "ultimo": contexto["hoje"]}
    try:
        objetos.gravar(contexto["nome"], json.dumps(estado).encode(), generation=contexto["generation"])
    except Exception:  # noqa: BLE001 - pior caso: o rodapé reaparece uma vez
        pass
