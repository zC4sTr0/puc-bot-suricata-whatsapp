"""Lease da rodada ativa da Suricata.

O contrato ativo usa CAS, o documento ``locks/rodada.lock`` e os campos
``dono``/``inicio``.
"""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .cas import CASConflict

LEASE = "locks/rodada.lock"


def _lease_minutos_do_ambiente() -> int:
    """Converte e valida o TTL do lease antes de iniciar o runtime."""
    try:
        minutos = int(os.environ.get("SURICATA_LEASE_MINUTOS", "6"))
    except ValueError as exc:
        raise ValueError("SURICATA_LEASE_MINUTOS deve ser inteiro não negativo")
    if minutos < 0:
        raise ValueError("SURICATA_LEASE_MINUTOS deve ser inteiro não negativo")
    return minutos


LEASE_MINUTOS = _lease_minutos_do_ambiente()


def _campo_json(dados: bytes, campo: str) -> Any:
    try:
        return json.loads(dados)[campo]
    except (KeyError, TypeError, ValueError):
        return None


class Lease:
    """Criação condicional; lease mais velho que ``LEASE_MINUTOS`` é abandonado."""

    def __init__(self, objetos: Any, agora: Callable[[], datetime]) -> None:
        self.objetos = objetos
        self.agora = agora
        self.generation: str | None = None

    def adquirir(self) -> bool:
        atual = self.objetos.ler(LEASE)
        if atual.dados is not None:
            # Relógio do servidor (``updated``) primeiro; conteúdo corrompido nunca
            # pode prender o lease para sempre: sem data legível, está abandonado.
            inicio = None
            for fonte in (atual.atualizado_em, _campo_json(atual.dados, "inicio")):
                try:
                    inicio = datetime.fromisoformat(str(fonte).replace("Z", "+00:00"))
                    break
                except (TypeError, ValueError):
                    continue
            if inicio is not None and self.agora() - inicio <= timedelta(minutes=LEASE_MINUTOS):
                return False
            if not self.objetos.apagar(LEASE, generation=atual.generation):
                return False
        dados = json.dumps({"dono": uuid.uuid4().hex, "inicio": self.agora().isoformat()}).encode()
        try:
            self.generation = self.objetos.gravar(LEASE, dados, generation=None)
        except CASConflict:
            return False
        return True

    def liberar(self) -> None:
        if self.generation is not None:
            try:
                self.objetos.apagar(LEASE, generation=self.generation)
            finally:
                self.generation = None
