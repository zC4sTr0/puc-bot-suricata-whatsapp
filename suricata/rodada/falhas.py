"""Dead-letter da rodada Suricata (contrato aditivo, T6).

Falhas que hoje só aparecem no relatório (envio sem ACK, coleta parcial)
ganham um rastro durável e sanitizado em ``falhas/falhas.jsonl`` no estado.
Cada linha é ``{momento, event_id?, etapa, erro_curto}`` — NUNCA payload,
token, JID, texto de mensagem ou dados pessoais. Escrever a dead-letter é
fail-safe: qualquer erro é engolido (devolve ``False``) e nunca derruba a
rodada nem muda exit code ou shape do relatório.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

NOME_FALHAS = "falhas/falhas.jsonl"
_LIMITE_ERRO = 200
_ETAPAS = frozenset({"coleta", "entrega", "memoria", "outbox"})

# Padrões que não podem sobreviver em nenhuma linha: JIDs, segredos, URLs.
_JID = re.compile(r"\b\d+(?:-\d+)?@(?:g\.us|s\.whatsapp\.net|c\.us)\b")
_SEGREDO = re.compile(r"(?i)\b(token|senha|secret|key|authorization|cookie)[=:]\S*")
_URL = re.compile(r"https?://\S+")
_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")


def sanitizar_erro(erro: Any) -> str:
    """Reduz um erro a texto curto e sanitizado (sem JID, segredo ou URL)."""
    texto = _CONTROLE.sub(" ", str(erro or ""))
    texto = _JID.sub("<jid>", texto)
    texto = _SEGREDO.sub(r"\1=<omitido>", texto)
    texto = _URL.sub("<url>", texto)
    return " ".join(texto.split())[:_LIMITE_ERRO]


def registrar_falhas(objetos: Any, falhas: list[dict], agora: datetime) -> bool:
    """Faz append sanitizado das falhas na dead-letter; nunca levanta.

    ``objetos`` é o backend CAS da rodada (``ler``/``gravar`` com geração).
    Devolve ``True`` se as linhas foram gravadas, ``False`` caso contrário
    (armazenamento indisponível, backend ausente ou lista vazia sem arquivo).
    """
    if not falhas:
        return False
    momento = agora.astimezone(timezone.utc).isoformat()
    linhas: list[str] = []
    for falha in falhas:
        if not isinstance(falha, dict):
            continue
        etapa = str(falha.get("etapa") or "desconhecida")[:40]
        if etapa not in _ETAPAS:
            etapa = "desconhecida"
        registro: dict[str, str] = {"momento": momento, "etapa": etapa}
        if falha.get("event_id"):
            registro["event_id"] = sanitizar_erro(falha["event_id"])
        registro["erro_curto"] = sanitizar_erro(falha.get("erro") or falha.get("detalhe"))
        linhas.append(json.dumps(registro, ensure_ascii=False))
    if not linhas:
        return False
    try:
        atual = objetos.ler(NOME_FALHAS)
        anteriores = (atual.dados.decode("utf-8") if atual.dados else "")
        if anteriores and not anteriores.endswith("\n"):
            anteriores += "\n"
        objetos.gravar(NOME_FALHAS, (anteriores + "\n".join(linhas) + "\n").encode("utf-8"),
                       generation=atual.generation)
    except Exception:  # noqa: BLE001 - fail-safe: dead-letter nunca derruba a rodada
        return False
    return True


__all__ = ["NOME_FALHAS", "registrar_falhas", "sanitizar_erro"]
