"""Tipos de valor compartilhados pelos backends de objetos CAS.

``Objeto`` é o tipo de retorno de ``ler`` dos dois backends (GCS e local) e o
insumo de ``SessaoWhatsApp``; mora em módulo próprio para que nenhum backend
dependa do outro apenas por causa do tipo compartilhado.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Objeto:
    dados: bytes | None
    generation: str | None
    atualizado_em: str | None = None
