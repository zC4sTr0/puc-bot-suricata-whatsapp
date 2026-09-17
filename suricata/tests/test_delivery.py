import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from suricata.delivery import DeliveryOrchestrator, DeliveryError
from suricata.message_id import message_id
from suricata.outbox import Outbox


NOW = datetime(2026, 9, 14, 12, tzinfo=timezone.utc)
GROUP = "120363000000000000@g.us"
EVENT = {
    "event_id": "quiz-42",
    "curso": "Ciência de Dados",
    "titulo": "Quiz de integração",
    "tipo": "quiz",
    "unlock_at": "2026-09-14T12:10:00Z",
}


class Runner:
    def __init__(self, result=None):
        self.calls = []
        self.result = result

    def __call__(self, group, events):
        self.calls.append((group, [dict(item) for item in events]))
        if self.result is not None:
            return self.result
        return {"sessao": "ok", "resultados": [
            {"event_id": item["event_id"], "message_id": item["message_id"],
             "ack": True, "status": 2}
            for item in events
        ]}


class WhatsAppShapeRunner:
    """Simula o retorno em lista do notificador WhatsApp real."""

    def __init__(self):
        self.calls = []

    def enviar_lote(self, grupo_jid, eventos):
        self.calls.append((grupo_jid, eventos))
        return [
            {"event_id": item["event_id"], "message_id": item["message_id"],
             "sessao": "ok", "ack": True, "status": 2}
            for item in eventos
        ]


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.outbox = Outbox(Path(self.tmp.name) / "outbox.json")

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, runner):
        return DeliveryOrchestrator(self.outbox, GROUP, runner, clock=lambda: NOW)

    def test_sucesso_persiste_sent_com_message_id_deterministico(self):
        runner = Runner()
        result = self.make(runner).deliver([EVENT])
        self.assertEqual(result[0]["estado"], "sent")
        self.assertEqual(result[0]["message_id"], message_id(GROUP, "quiz-42"))
        self.assertEqual(runner.calls[0][1][0]["message_id"], message_id(GROUP, "quiz-42"))

    def test_timeout_preserva_pending_e_mesmo_id_pode_ser_reivindicado(self):
        runner = Runner({"sessao": "timeout", "resultados": []})
        result = self.make(runner).deliver([EVENT])
        self.assertEqual(result[0]["estado"], "pending")
        self.assertEqual(self.outbox.pendentes()[0]["message_id"], message_id(GROUP, "quiz-42"))

    def test_ack_estrangeiro_preserva_pending(self):
        runner = Runner({"sessao": "ok", "resultados": [
            {"event_id": "outro", "message_id": message_id(GROUP, "outro"), "ack": True, "status": 2}
        ]})
        result = self.make(runner).deliver([EVENT])
        self.assertEqual(result[0]["estado"], "pending")
        self.assertEqual(len(runner.calls), 1)

    def test_duplicata_idempotente_nao_reenvia_evento_sent(self):
        runner = Runner()
        orchestrator = self.make(runner)
        first = orchestrator.deliver([EVENT])
        second = orchestrator.deliver([dict(EVENT)])
        self.assertEqual(first[0]["estado"], "sent")
        self.assertEqual(second[0]["estado"], "sent")
        self.assertEqual(len(runner.calls), 1)

    def test_evento_expirado_nao_e_reivindicado(self):
        expired = dict(EVENT, expira_em=(NOW - timedelta(seconds=1)).isoformat())
        runner = Runner()
        result = self.make(runner).deliver([expired])
        self.assertEqual(result[0]["estado"], "expirado")
        self.assertEqual(runner.calls, [])

    def test_allowlist_publica_rejeita_campo_privado(self):
        with self.assertRaises(DeliveryError):
            self.make(Runner()).deliver([dict(EVENT, nota=10)])

    def test_resultado_malformado_preserva_pending(self):
        runner = Runner({"sessao": "ok", "resultados": [{"ack": True}]})
        result = self.make(runner).deliver([EVENT])
        self.assertEqual(result[0]["estado"], "pending")

    def test_retorno_em_lista_do_whatsapp_real_confirma_sent(self):
        runner = WhatsAppShapeRunner()
        result = self.make(runner).deliver([EVENT])
        self.assertEqual(result[0]["estado"], "sent")
        self.assertEqual(runner.calls[0][0], GROUP)


if __name__ == "__main__":
    unittest.main()
