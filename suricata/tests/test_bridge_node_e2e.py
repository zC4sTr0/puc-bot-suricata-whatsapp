import unittest
from pathlib import Path

from suricata.bridge import WhatsAppBridge
from suricata.message_id import message_id
from suricata.storage.cas import AuthSnapshot


GROUP = "120363000000000000@g.us"
ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "tests" / "fixtures" / "bridge_ack_stub.mjs"


class LocalSessionStorage:
    def __init__(self):
        self.auth = {"creds.json": '{"client":"offline"}'}
        self.generation = "1"
        self.writes = []

    def read_auth(self):
        return AuthSnapshot(dict(self.auth), self.generation)

    def write_auth(self, value, *, expected_generation):
        self.writes.append((value, expected_generation))
        self.auth = dict(value)
        self.generation = "2"
        return AuthSnapshot(dict(self.auth), self.generation)


class PythonToNodeOfflineE2ETests(unittest.TestCase):
    def test_bridge_real_inicia_node_stub_confirma_ack_e_persiste_sessao(self):
        storage = LocalSessionStorage()
        bridge = WhatsAppBridge(storage, script=STUB, timeout=5)
        evento = {
            "event_id": "quiz-offline-1",
            "message_id": message_id(GROUP, "quiz-offline-1"),
            "texto": "Aviso offline",
        }

        resultado = bridge.enviar_lote(GROUP, [evento])

        self.assertEqual(resultado["sessao"], "ok")
        self.assertEqual(resultado["resultados"][0]["ack"], True)
        self.assertEqual(storage.writes[0][0]["creds.json"], '{"client":"offline","stub_used":true}')
        self.assertEqual(storage.writes[0][1], "1")

    def test_bridge_node_stub_recebe_somente_contrato_publico(self):
        storage = LocalSessionStorage()
        bridge = WhatsAppBridge(storage, script=STUB, timeout=5)
        evento = {
            "event_id": "evento-unicode",
            "message_id": message_id(GROUP, "evento-unicode"),
            "texto": "Atenção: café às 19h",
        }

        resultado = bridge.enviar_lote(GROUP, [evento])

        self.assertEqual(resultado["resultados"][0]["event_id"], "evento-unicode")
        self.assertEqual(resultado["resultados"][0]["message_id"], evento["message_id"])


if __name__ == "__main__":
    unittest.main()
