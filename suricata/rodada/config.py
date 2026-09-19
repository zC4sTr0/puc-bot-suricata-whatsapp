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
from pathlib import Path

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


def _carregar_config_arquivo(caminho: str) -> dict:
    """Lê e valida ``SURICATA_CONFIG``; qualquer falha é ValueError fail-closed."""
    try:
        texto = Path(caminho).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"SURICATA_CONFIG: arquivo não pôde ser lido: {caminho}") from exc
    try:
        dados = json.loads(texto)
    except ValueError as exc:
        raise ValueError("SURICATA_CONFIG: JSON inválido") from exc
    destinos = dados.get("destinos") if isinstance(dados, dict) else None
    if not isinstance(destinos, list) or not all(isinstance(i, dict) for i in destinos):
        raise ValueError('SURICATA_CONFIG: schema inválido; esperado {"destinos": [...]}')
    if not destinos:
        raise ValueError("SURICATA_CONFIG: nenhum destino configurado no arquivo")
    for item in destinos:
        if not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("SURICATA_CONFIG: destino sem id")
        if not isinstance(item.get("jid"), str) or not item["jid"].strip():
            raise ValueError("SURICATA_CONFIG: destino sem jid")
    lease = dados.get("lease_minutos")
    if lease is not None and (isinstance(lease, bool) or not isinstance(lease, int) or lease < 1):
        raise ValueError("SURICATA_CONFIG: lease_minutos deve ser inteiro >= 1")
    return dados


def _ambiente_com_arquivo(ambiente: dict[str, str]) -> dict[str, str]:
    """Integra ``SURICATA_CONFIG``: arquivo é a base, env de destino sobrepõe."""
    dados = _carregar_config_arquivo(ambiente["SURICATA_CONFIG"])
    sintetico = {chave: valor for chave, valor in ambiente.items()
                 if chave not in {"SURICATA_GRUPO_JID", "SURICATA_DESTINOS_JSON",
                                  "SURICATA_DESTINOS"}}
    adicionais: list[dict] = []
    for item in dados["destinos"]:
        if item.get("id") == "grupo":
            sintetico.setdefault("SURICATA_GRUPO_JID", item.get("jid") or "")
        else:
            adicional = {"id": item.get("id"), "jid": item.get("jid")}
            if item.get("janela_brt"):
                adicional["janela_brt"] = item["janela_brt"]
            adicionais.append(adicional)
    if adicionais:
        sintetico["SURICATA_DESTINOS_JSON"] = json.dumps(adicionais)
    # Precedência env > arquivo: variáveis de destino presentes no ambiente
    # real sobrescrevem o que veio do arquivo.
    for chave in ("SURICATA_GRUPO_JID", "SURICATA_DESTINOS_JSON", "SURICATA_DESTINOS"):
        if ambiente.get(chave):
            sintetico[chave] = ambiente[chave]
    return sintetico


def destinos_do_ambiente(env: dict[str, str] | None = None) -> list[Destino]:
    """Lê destinos sem nomes/JIDs no código.

    ``SURICATA_GRUPO_JID`` é o destino legado. Destinos adicionais são um
    JSON opt-in em ``SURICATA_DESTINOS_JSON`` (ou ``SURICATA_DESTINOS``),
    com itens ``{"id": "...", "jid": "..."}`` ou uma janela BRT opcional.
    O identificador só pode formar um segmento de caminho seguro.

    ``SURICATA_CONFIG`` aponta opcionalmente para um arquivo JSON
    ``{"destinos": [...], "lease_minutos": N?}``: os destinos do arquivo
    são a base e as env vars de destino, quando presentes, sobrepõem
    (env > arquivo). Arquivo ausente/inválido é fail-closed. ``lease_minutos``
    do arquivo é aceito e validado, mas NÃO aplicado: ``LEASE_MINUTOS``
    continua lido do ambiente no import de ``suricata.storage.lease_rodada``
    (limitação documentada para não mover a leitura de forma invasiva).
    """
    ambiente = os.environ if env is None else env
    if ambiente.get("SURICATA_CONFIG"):
        ambiente = _ambiente_com_arquivo(ambiente)
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
