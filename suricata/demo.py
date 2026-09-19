"""Modo demo: a rodada da Suricata offline, zero-config e sem efeito externo.

Um estudante roda ``python -m suricata --mode demo`` sem NENHUMA variável de
ambiente e vê o pipeline de produção funcionar de ponta a ponta:

- Canvas congelado: a fixture pública e sintética
  ``tests/fixtures/canvas_demo.json`` é servida por um transporte local;
  nenhum socket é aberto;
- estado real (lease CAS, memória, relatório) em ``TemporaryDirectory`` —
  nasce e morre com o processo;
- entrega DESLIGADA: a ponte nunca é construída (padrão de
  ``test_caminho_real_e2e`` com ``SURICATA_ENTREGA=desligada``);
- relógio fixo (ter 15/09/2026, véspera) — a saída é determinística.

Duas rodadas simulam o Cloud Run: a primeira é linha de base (registra,
não anuncia); na segunda, dez minutos depois, um quiz-relâmpago foi
publicado e é 18:00 de Brasília — a hora da véspera. As mensagens
PLANEJADAS (o que seria enviado) e o relatório vão ao stdout, seguidos da
linha explícita de entrega desligada. Nada é enviado a ninguém.
"""
from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .integracao.canvas import CanvasClient
from .rodada.execucao import executar
from .storage.gcs import ObjetosLocais

_FIXTURE = Path(__file__).resolve().parent / "tests" / "fixtures" / "canvas_demo.json"

# Relógio congelado (determinismo): terça 15/09/2026, 17:50 de Brasília.
_BASE = datetime(2026, 9, 15, 20, 50, tzinfo=timezone.utc)
_RODADA_2 = _BASE + timedelta(minutes=10)  # 18:00 de Brasília: hora da véspera


class _CanvasCongelado:
    """Transporte local que serve os dados da fixture; nenhum socket é aberto."""

    def __init__(self, dados: Mapping[str, Any]) -> None:
        self._cursos = list(dados["cursos"])
        self._anuncios = list(dados.get("anuncios", []))
        self.itens: dict[str, list[dict[str, Any]]] = {
            str(curso): list(itens) for curso, itens in dados["assignments"].items()
        }

    def publicar_novidades(self, novidades: Mapping[str, list[dict[str, Any]]]) -> None:
        """Aplica os itens que 'aparecem' entre a rodada 1 e a rodada 2."""
        for curso, itens in novidades.items():
            self.itens[curso] = self.itens.get(curso, []) + list(itens)

    def cliente(self) -> CanvasClient:
        return CanvasClient(token="demo", transport=self._transporte)

    def _transporte(self, method: str, url: str, headers: Mapping[str, str],
                     timeout: float) -> tuple[int, Mapping[str, str], list[Any]]:
        if "/announcements" in url:
            return 200, {}, self._anuncios
        if "/assignments" in url:
            curso = url.split("/courses/")[1].split("/")[0]
            return 200, {}, self.itens.get(curso, [])
        return 200, {}, self._cursos


def main() -> int:
    dados = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    canvas = _CanvasCongelado(dados)
    print("suricata · modo demo — Canvas congelado da fixture, relógio fixo em 15/09/2026,")
    print("estado temporário, entrega desligada. Nada sai deste processo.")
    with tempfile.TemporaryDirectory(prefix="suricata-demo-") as estado:
        objetos = ObjetosLocais(Path(estado))
        cliente = canvas.cliente()
        # Rodada 1 (17:50 BRT): primeira rodada é linha de base — registra, não anuncia.
        executar(objetos=objetos, canvas=cliente, entrega_ligada=False,
                 grupo_jid=None, ponte=None, agora=lambda: _BASE)
        # Rodada 2 (18:00 BRT): um quiz-relâmpago foi publicado e é a hora da véspera.
        canvas.publicar_novidades(dados.get("novidades", {}))
        codigo, relatorio = executar(objetos=objetos, canvas=cliente, entrega_ligada=False,
                                     grupo_jid=None, ponte=None, agora=lambda: _RODADA_2)

        print()
        print("mensagens planejadas (o que seria enviado ao grupo):")
        if relatorio["eventos"]:
            for evento in relatorio["eventos"]:
                print()
                print(f"--- {evento['tipo']} · {evento['event_id']}")
                print(evento["texto"])
        else:
            print("(nenhuma mensagem planejada nesta rodada)")
        print()
        print("relatório da rodada:")
        print(json.dumps(relatorio, ensure_ascii=False, indent=1, sort_keys=True))
        print()
        print("entrega: desligada — nenhum envio foi feito; nenhum Canvas, WhatsApp ou rede foi acessado.")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
