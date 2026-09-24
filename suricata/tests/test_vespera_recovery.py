from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from suricata.dominio.corte_rodada import autorizados_persistidos
from suricata.dominio.message_id import message_id
from suricata.dominio.planejamento import Evento
from suricata.rodada.execucao import _registrar_eventos
from suricata.storage.outbox import Outbox

JID = "120363000000000000-1700000000@g.us"


class TestVesperaRecovery(unittest.TestCase):
    def test_registro_de_vespera_cria_janela_tecnica_ate_07h31(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "outbox.json"
            fila = SimpleNamespace(caminho=caminho)
            outbox = Outbox(caminho)
            evento = Evento("vespera", "grupo:vespera:2026-09-21", "aviso da véspera",
                            "2026-09-21T10:30:00+00:00")
            _registrar_eventos(fila, outbox, JID, [evento], datetime(2026, 9, 20, 21, tzinfo=timezone.utc))
            registro = outbox.pendentes()[0]
            self.assertEqual(registro["tipo"], "vespera")
            self.assertEqual(registro["expira_em"], "2026-09-21T10:31:00+00:00")
            self.assertEqual(registro["recuperacao_manha"]["data"], "2026-09-21")

    def test_vespera_sem_ack_atravessa_21h_e_fica_autorizada_as_07h30(self):
        with tempfile.TemporaryDirectory() as tmp:
            outbox = Outbox(Path(tmp) / "outbox.json")
            evento_id = "grupo:vespera:2026-09-21"
            outbox.adicionar({
                "event_id": evento_id,
                "message_id": message_id(JID, evento_id),
                "texto": "aviso da véspera",
                "tipo": "vespera",
                "recuperacao_manha": {
                    "tipo": "vespera",
                    "data": "2026-09-21",
                    "expira_em": "2026-09-21T10:31:00+00:00",
                },
                "expira_em": "2026-09-21T10:31:00+00:00",
            }, agora=datetime(2026, 9, 20, 21, tzinfo=timezone.utc))
            fila = SimpleNamespace(outbox=outbox)
            as_21 = datetime(2026, 9, 21, 0, tzinfo=timezone.utc)  # 21:00 BRT do dia anterior
            autorizados = autorizados_persistidos(fila, [], as_21)
            corte = outbox.cortar_apos_21h(agora=as_21, autorizados=autorizados)
            self.assertEqual(corte["expirados"], 0)
            self.assertEqual(outbox.pendentes()[0]["event_id"], evento_id)

            as_07 = datetime(2026, 9, 21, 10, 30, 20, tzinfo=timezone.utc)
            self.assertIn(evento_id, autorizados_persistidos(fila, [], as_07))

    def test_marcador_de_recuperacao_forjado_nao_autoriza_evento_comum(self):
        with tempfile.TemporaryDirectory() as tmp:
            outbox = Outbox(Path(tmp) / "outbox.json")
            outbox.adicionar({
                "event_id": "grupo:novo:fraudado",
                "message_id": message_id(JID, "grupo:novo:fraudado"),
                "texto": "não deve atravessar",
                "tipo": "novo",
                "recuperacao_manha": {
                    "tipo": "vespera",
                    "data": "2026-09-21",
                    "expira_em": "2026-09-21T10:31:00+00:00",
                },
                "expira_em": "2026-09-21T10:31:00+00:00",
            }, agora=datetime(2026, 9, 20, 21, tzinfo=timezone.utc))
            fila = SimpleNamespace(outbox=outbox)
            as_21 = datetime(2026, 9, 21, 0, tzinfo=timezone.utc)
            self.assertEqual(autorizados_persistidos(fila, [], as_21), set())


if __name__ == "__main__":
    unittest.main()
