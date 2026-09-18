from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path

from suricata.storage.outbox import Outbox, OutboxError


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.path = Path(self.root.name) / "grupo" / "outbox.json"
        self.now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        self.event = {"event_id": "e1", "message_id": "3EB0A1B2C3D4E5F6071829", "texto": "aviso", "expira_em": (self.now + timedelta(hours=1)).isoformat()}

    def tearDown(self): self.root.cleanup()

    def test_idempotencia_e_transicoes(self):
        outbox = Outbox(self.path)
        first = outbox.adicionar(self.event, agora=self.now)
        again = outbox.adicionar(self.event, agora=self.now)
        self.assertEqual(first, again)
        outbox.transicionar("e1", "in_flight", agora=self.now)
        with self.assertRaises(OutboxError): outbox.transicionar("e1", "sent", agora=self.now)
        sent = outbox.transicionar("e1", "sent", ack=True, agora=self.now)
        self.assertEqual(sent["estado"], "sent")
        with self.assertRaises(OutboxError): outbox.transicionar("e1", "pending", agora=self.now)

    def test_crash_in_flight_volta_a_pending(self):
        outbox = Outbox(self.path)
        outbox.adicionar(self.event, agora=self.now)
        outbox.transicionar("e1", "in_flight", agora=self.now)
        self.assertEqual(outbox.recuperar_interrompidos(agora=self.now + timedelta(minutes=5))[0]["estado"], "pending")
        self.assertEqual(Outbox(self.path).pendentes()[0]["message_id"], self.event["message_id"])

    def test_crash_depois_do_prazo_expira_e_nao_reenvia(self):
        outbox = Outbox(self.path)
        expired = {**self.event, "expira_em": (self.now - timedelta(minutes=1)).isoformat()}
        outbox.adicionar(expired, agora=self.now - timedelta(hours=1))
        outbox.transicionar("e1", "in_flight", agora=self.now - timedelta(hours=1))
        self.assertEqual(outbox.recuperar_interrompidos(agora=self.now)[0]["estado"], "pending")
        self.assertEqual(outbox.expirar(agora=self.now)[0]["estado"], "expirado")

    def test_claim_tem_fencing_e_resultado_tardio_e_rejeitado(self):
        outbox = Outbox(self.path)
        outbox.adicionar(self.event, agora=self.now)
        attempt = outbox.reivindicar("e1", agora=self.now)
        with self.assertRaises(OutboxError):
            outbox.aplicar_resultado("e1", attempt_id="stale", message_id=self.event["message_id"], ack=True, status=2)
        sent = outbox.aplicar_resultado("e1", attempt_id=attempt["attempt_id"], message_id=self.event["message_id"], ack=True, status=2)
        self.assertEqual(sent["estado"], "sent")

    def test_reutilizacao_de_event_id_com_conteudo_diferente_falha(self):
        outbox = Outbox(self.path)
        outbox.adicionar(self.event, agora=self.now)
        with self.assertRaises(OutboxError): outbox.adicionar({**self.event, "texto": "outro"}, agora=self.now)

    def test_expira_somente_depois_do_prazo(self):
        outbox = Outbox(self.path)
        outbox.adicionar(self.event, agora=self.now)
        self.assertEqual(outbox.expirar(agora=self.now), [])
        expired = outbox.expirar(agora=self.now + timedelta(hours=2))
        self.assertEqual(expired[0]["estado"], "expirado")

    def test_proibe_unknown_failed_e_sent_sem_ack(self):
        outbox = Outbox(self.path)
        outbox.adicionar(self.event, agora=self.now)
        for state in ("unknown", "failed"):
            with self.assertRaises(OutboxError): outbox.transicionar("e1", state)
        outbox.transicionar("e1", "in_flight")
        with self.assertRaises(OutboxError): outbox.transicionar("e1", "sent")


if __name__ == "__main__": unittest.main()
