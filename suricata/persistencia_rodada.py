"""Persistência CAS do outbox usado pela rodada da Suricata."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .outbox import Outbox

OUTBOX = "grupo/outbox.json"
RETENCAO = timedelta(days=30)


class OutboxSincronizado:
    """Usa o ``Outbox`` testado num arquivo temporário e o publica por CAS.

    O lease garante um escritor por vez; um conflito de geração significa que
    outra rodada assumiu, e a rodada atual para antes de qualquer envio.
    """

    def __init__(self, objetos: Any, pasta: Path, nome: str = OUTBOX) -> None:
        self.objetos = objetos
        self.nome = nome
        self.caminho = pasta / "outbox.json"
        obj = objetos.ler(nome)
        self.generation = obj.generation
        self._publicado = obj.dados
        if obj.dados is not None:
            self.caminho.write_bytes(obj.dados)
        self.outbox = Outbox(self.caminho)

    def publicar(self) -> None:
        dados = self.caminho.read_bytes() if self.caminho.exists() else None
        if dados is None or dados == self._publicado:
            return
        self.generation = self.objetos.gravar(self.nome, dados, generation=self.generation)
        self._publicado = dados

    def podar(self, agora: datetime) -> None:
        """Remove ``sent``/``expirado`` antigos para o documento não crescer sem limite."""
        if not self.caminho.exists():
            return
        registros = json.loads(self.caminho.read_text(encoding="utf-8"))
        limite = agora - RETENCAO
        mantidos = [r for r in registros if r["estado"] in {"pending", "in_flight"}
                    or datetime.fromisoformat(r.get("atualizado_em") or r["criado_em"]) > limite]
        if len(mantidos) != len(registros):
            self.caminho.write_text(json.dumps(mantidos, ensure_ascii=False, separators=(",", ":")) + "\n",
                                    encoding="utf-8")
            self.outbox = Outbox(self.caminho)
