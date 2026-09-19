"""E2E offline da rodada completa: planejamento → outbox REAL → ponte Node REAL.

Diferente de ``test_bridge_node_e2e.py`` (só a fronteira) e de
``test_caminho_real_e2e.py`` (entrega desligada), aqui a rodada inteira
percorre ``run_from_environment`` com injeção explícita de fábricas:

- Canvas falso (transporte em memória) — o único double;
- ``ObjetosLocais`` sobre ``TemporaryDirectory`` — estado 100% temporário;
- ``WhatsAppBridge`` REAL com o stub Node versionado
  (``tests/fixtures/bridge_stub.mjs``) como subprocesso de verdade;
- cenário do stub escolhido pelo campo ``stub_scenario`` do ``creds.json``
  da sessão (precedência 3 do stub) — nada de env var de produção;
- relógio congelado por injeção em ``executar`` (10:00 BRT, janela válida).

Zero rede: o único processo externo é o Node local rodando o stub, que só
lê/escreve no ``auth_dir`` do próprio lote.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from suricata.integracao.bridge import WhatsAppBridge
from suricata.integracao.canvas import CanvasClient
from suricata.rodada import executar, run_from_environment
from suricata.rodada.config import destinos_do_ambiente
from suricata.storage.gcs import ObjetosLocais, SessaoWhatsApp

RAIZ = Path(__file__).resolve().parents[1]
STUB = RAIZ / "tests" / "fixtures" / "bridge_stub.mjs"
JID = "120363000000000000-1700000000@g.us"
# 10:00 de Brasília: dentro da janela 07:00–21:00, fora do corte das 21h.
AGORA = datetime(2026, 9, 18, 13, 0, tzinfo=timezone.utc)


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


class PonteEspia:
    """Envolve a ponte REAL (Node subprocessado) e conta os lotes enviados."""

    def __init__(self, storage, node: str, registro: list):
        self.interna = WhatsAppBridge(storage, node=node, script=STUB, timeout=20)
        self.registro = registro

    def enviar_lote(self, grupo_jid, eventos):
        self.registro.append(json.loads(json.dumps(eventos)))
        return self.interna.enviar_lote(grupo_jid, eventos)


class E2ERodadaOfflineTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("node") is None:  # ambiente sem Node: suíte continua incondicional no CI
            self.skipTest("node indisponível")
        self._tmp = tempfile.TemporaryDirectory(prefix="suricata-e2e-")
        self.estado = Path(self._tmp.name)
        self.objetos = ObjetosLocais(str(self.estado))
        self.node = shutil.which("node") or "node"
        self.cenario = "sucesso"
        self.lotes: list[list[dict]] = []
        self.itens: list[dict] = []
        self._sementar_sessao()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ---------- infraestrutura ----------

    def _sementar_sessao(self) -> None:
        atual = self.objetos.ler("whatsapp/auth.json")
        self.objetos.gravar("whatsapp/auth.json",
                            json.dumps({"creds.json": json.dumps({"creds": "offline",
                                                                  "stub_scenario": self.cenario})}).encode(),
                            generation=atual.generation)

    def _reseedar_sessao(self, cenario: str) -> None:
        atual = self.objetos.ler("whatsapp/auth.json")
        valor = json.loads(atual.dados.decode())
        valor["creds.json"] = json.dumps({"creds": "offline", "stub_scenario": cenario})
        self.objetos.gravar("whatsapp/auth.json", json.dumps(valor).encode(), generation=atual.generation)

    def _creds(self) -> dict:
        bruto = self._auth().get("creds.json")
        return json.loads(bruto) if bruto else {}

    def _quiz(self, ident: int = 9001) -> dict:
        return {"id": ident, "name": "Quiz relâmpago", "points_possible": 3, "quiz_id": 555,
                "due_at": None,
                "unlock_at": _iso(AGORA + timedelta(hours=1)),
                "lock_at": _iso(AGORA + timedelta(hours=1, minutes=30)),
                "submission_types": ["online_quiz"],
                "html_url": f"https://canvas.example.test/courses/100001/assignments/{ident}"}

    def _transporte(self, method, url, headers, timeout):
        if "/announcements" in url:
            return 200, {}, []
        if "/assignments" in url:
            curso = url.split("/courses/")[1].split("/")[0]
            return 200, {}, self.itens if curso == "100001" else []
        return 200, {}, [{"id": 100001, "name": "Computabilidade"}]

    def _rodada(self, *, entrega: bool = True) -> tuple[int, dict]:
        ambiente = {"SURICATA_ESTADO_URI": str(self.estado), "SURICATA_CANVAS_TOKEN": "falso",
                    "SURICATA_GRUPO_JID": JID,
                    "SURICATA_ENTREGA": "ligada" if entrega else "desligada"}
        saida = io.StringIO()
        usada: dict = {}

        def single_runner(**kwargs):
            return executar(agora=lambda: AGORA, **kwargs)

        def bridge_factory(storage):
            usada["ponte"] = PonteEspia(storage, self.node, self.lotes)
            return usada["ponte"]

        with mock.patch.dict(os.environ, ambiente), contextlib.redirect_stdout(saida):
            codigo = run_from_environment(
                canvas_factory=lambda: CanvasClient(token="falso", transport=self._transporte),
                destinations_factory=destinos_do_ambiente,
                objects_factory=lambda uri: self.objetos,
                session_factory=SessaoWhatsApp,
                bridge_factory=bridge_factory,
                single_runner=single_runner,
                multi_runner=lambda **kwargs: executar(agora=lambda: AGORA, **kwargs),
            )
        relatorio = json.loads(saida.getvalue().strip().splitlines()[-1])
        return codigo, relatorio

    def _outbox(self) -> list[dict]:
        obj = self.objetos.ler("grupo/outbox.json")
        return json.loads(obj.dados.decode()) if obj.dados else []

    def _auth(self) -> dict:
        obj = self.objetos.ler("whatsapp/auth.json")
        return json.loads(obj.dados.decode()) if obj.dados else {}

    # ---------- cenários ----------

    def test_a_ack_valido_marca_sent_no_outbox_real_com_subprocesso_node(self):
        codigo, _ = self._rodada()  # linha de base: nada anuncia
        self.assertEqual(codigo, 0)
        self.itens = [self._quiz()]
        codigo, relatorio = self._rodada()
        self.assertEqual(codigo, 0)
        self.assertEqual(relatorio["eventos"][0]["tipo"], "novo")
        self.assertEqual(relatorio["entrega"]["sent"], 1)
        self.assertEqual(relatorio["entrega"]["sessao"], "ok")
        registros = self._outbox()
        self.assertEqual([r["estado"] for r in registros], ["sent"])
        self.assertTrue(registros[0]["message_id"].startswith("3EB0"))
        # O subprocesso Node REAL rodou: o stub marcou a sessão persistida.
        self.assertTrue(self._creds().get("stub_used") is True)
        lote = self.lotes[0]
        self.assertEqual(lote[0]["event_id"], "grupo:novo:100001:9001")

    def test_b_reexecucao_idempotente_nao_reenvia_memoria_consumida(self):
        self._rodada()
        self.itens = [self._quiz()]
        codigo, primeiro = self._rodada()
        self.assertEqual(primeiro["entrega"]["sent"], 1)
        lotes_apos_primeira = len(self.lotes)
        codigo, segundo = self._rodada()
        self.assertEqual(codigo, 0)
        self.assertEqual(segundo["eventos"], [])
        self.assertEqual(segundo["entrega"]["pendentes_enviados"], 0)
        self.assertEqual(segundo["entrega"]["sent"], 0)
        self.assertEqual(len(self.lotes), lotes_apos_primeira)

    def test_c_timeout_volta_pending_nada_como_sent(self):
        self.cenario = "timeout"
        self._sementar_sessao()
        self._rodada()
        self.itens = [self._quiz()]
        codigo, relatorio = self._rodada()
        self.assertEqual(codigo, 6)
        self.assertEqual(relatorio["entrega"]["sem_ack"], 1)
        self.assertEqual(relatorio["entrega"]["sent"], 0)
        self.assertEqual(relatorio["entrega"]["sessao"], "timeout")
        registros = self._outbox()
        self.assertEqual([r["estado"] for r in registros], ["pending"])
        # Sessão não persistida: o stub de timeout não escreve nada no auth.
        self.assertNotIn("stub_used", self._creds())

    def test_d_ack_divergente_e_recusado_sem_persistir_sessao(self):
        self.cenario = "ack-divergente"
        self._sementar_sessao()
        self._rodada()
        self.itens = [self._quiz()]
        codigo, relatorio = self._rodada()
        self.assertEqual(codigo, 6)
        self.assertEqual(relatorio["entrega"]["sent"], 0)
        self.assertEqual(relatorio["entrega"]["sem_ack"], 1)
        registros = self._outbox()
        self.assertEqual([r["estado"] for r in registros], ["pending"])
        self.assertNotIn("stub_used", self._creds())

    def test_e_entrega_desligada_nunca_chama_a_ponte(self):
        codigo, relatorio = self._rodada(entrega=False)
        self.assertEqual(codigo, 0)
        self.itens = [self._quiz()]
        codigo, relatorio = self._rodada(entrega=False)
        self.assertEqual(codigo, 0)
        self.assertEqual(relatorio["eventos"][0]["tipo"], "novo")
        self.assertEqual(self.lotes, [])
        self.assertIsNone(self.objetos.ler("grupo/outbox.json").dados)


if __name__ == "__main__":
    unittest.main()
