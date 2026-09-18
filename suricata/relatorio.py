"""Relatório público e sanitizado de uma rodada Suricata."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Relatorio:
    """Estado observável da rodada sem expor referências mutáveis internas."""

    iniciado_em: str
    modo: str
    estado: str = "iniciada"
    ofertas: int = 0
    ofertas_com_falha: list[str] = field(default_factory=list)
    atividades: int = 0
    linha_de_base: bool = False
    eventos: list[dict[str, str]] = field(default_factory=list)
    entrega: dict[str, Any] = field(default_factory=dict)
    agenda_manual: dict[str, Any] = field(default_factory=dict)
    coleta: dict[str, Any] = field(default_factory=dict)
    erro: str | None = None

    def json(self) -> dict[str, Any]:
        return {
            "iniciado_em": self.iniciado_em,
            "modo": self.modo,
            "estado": self.estado,
            "ofertas": self.ofertas,
            "ofertas_com_falha": deepcopy(self.ofertas_com_falha),
            "atividades": self.atividades,
            "linha_de_base": self.linha_de_base,
            "eventos": deepcopy(self.eventos),
            "entrega": deepcopy(self.entrega),
            "agenda_manual": deepcopy(self.agenda_manual),
            "coleta": deepcopy(self.coleta),
            "erro": self.erro,
        }


__all__ = ["Relatorio"]
