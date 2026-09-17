import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from suricata.message_id import message_id
from suricata.bridge import BridgeError, WhatsAppBridge
from suricata.notifiers.whatsapp import WhatsAppGrupo, entregar_grupo
from suricata.outbox import Outbox


NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
GROUP = "120363000000000000@g.us"


class FakeBridge:
    """Double local: simula ACK, timeout e identidade estrangeira."""

    def __init__(self, mode="success"):
        self.mode = mode
        self.calls = []

    def enviar_lote(self, grupo_jid, eventos):
        self.calls.append((grupo_jid, [dict(evento) for evento in eventos]))
        if self.mode == "timeout":
            return {
                "sessao": "timeout",
                "resultados": [
                    {"event_id": eventos[0]["event_id"], "message_id": eventos[0]["message_id"], "ack": False}
                ],
            }
        if self.mode == "foreign_ack":
            return {
                "sessao": "ok",
                "resultados": [
                    {
                        "event_id": "evento-estrangeiro",
                        "message_id": message_id(grupo_jid, "evento-estrangeiro"),
                        "ack": True,
                        "status": 2,
                    }
                ],
            }
        return {
            "sessao": "ok",
            "resultados": [
                {
                    "event_id": evento["event_id"],
                    "message_id": evento["message_id"],
                    "ack": True,
                    "status": 2,
                }
                for evento in eventos
            ],
        }


class BridgeOutboxIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.outbox = Outbox(Path(self.root.name) / "outbox.json")
        self.event = {
            "event_id": "quiz-42",
            "curso": "Ciência de Dados",
            "titulo": "Quiz de integração",
            "tipo": "quiz",
            "unlock_at": "2026-09-14T12:10:00Z",
        }

    def tearDown(self):
        self.root.cleanup()

    def _deliver(self, mode="success"):
        double = FakeBridge(mode)
        notifier = WhatsAppGrupo(self.outbox, GROUP, bridge=double)
        result = entregar_grupo(self.outbox, notifier, [self.event], momento=NOW)
        return double, result

    def test_evento_publico_gera_message_id_e_outbox_e_ack_confirma_sent(self):
        double, result = self._deliver()

        self.assertEqual(result[0]["estado"], "sent")
        self.assertEqual(result[0]["message_id"], message_id(GROUP, "quiz-42"))
        self.assertEqual(result[0]["event_id"], "quiz-42")
        self.assertEqual(double.calls[0][0], GROUP)
        self.assertEqual(double.calls[0][1][0]["message_id"], message_id(GROUP, "quiz-42"))
        self.assertEqual(self.outbox.pendentes(), [])

    def test_timeout_preserva_pending_e_pode_ser_reivindicado_novamente(self):
        double, result = self._deliver("timeout")

        self.assertEqual(result[0]["estado"], "pending")
        self.assertEqual(len(double.calls), 1)
        retry = self.outbox.reivindicar("quiz-42", agora=NOW)
        self.assertEqual(retry["estado"], "in_flight")
        self.assertEqual(retry["message_id"], message_id(GROUP, "quiz-42"))

    def test_ack_de_evento_estrangeiro_eh_fail_closed_e_preserva_pending(self):
        double, result = self._deliver("foreign_ack")

        self.assertEqual(result[0]["estado"], "pending")
        self.assertEqual(result[0]["message_id"], message_id(GROUP, "quiz-42"))
        self.assertEqual(self.outbox.pendentes()[0]["event_id"], "quiz-42")

    def test_double_injetado_nao_invoca_node_real(self):
        double, _ = self._deliver()

        self.assertEqual(len(double.calls), 1)
        self.assertIsInstance(double, FakeBridge)

    def test_bridge_rejeita_event_id_duplicado_antes_de_tocar_runner(self):
        storage = type("Storage", (), {})()
        runner = lambda *_args, **_kwargs: self.fail("runner não deveria ser chamado")
        evento = {
            "event_id": "duplicado",
            "message_id": message_id(GROUP, "duplicado"),
            "texto": "aviso",
        }

        with self.assertRaises(BridgeError):
            WhatsAppBridge(storage, run=runner).enviar_lote(GROUP, [evento, dict(evento)])


if __name__ == "__main__":
    unittest.main()
