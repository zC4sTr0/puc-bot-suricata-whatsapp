"""E2E offline da fronteira Python -> Node com o stub versionado da ponte.

O stub (``tests/fixtures/bridge_stub.mjs``) é um processo Node REAL, iniciado
pelo ``WhatsAppBridge`` via stdin/stdout, mas sem Baileys e sem rede: os ACKs
são controlados por cenário (sucesso, timeout, ACK divergente, crash) via
marcador ``[stub:<cenario>]`` no campo ``texto`` do lote. O teste é
incondicional: a fixture vive no repositório.
"""
import unittest
from pathlib import Path

from suricata.dominio.message_id import message_id
from suricata.integracao.bridge import BridgeError, WhatsAppBridge
from suricata.storage.cas import AuthSnapshot

GROUP = "120363000000000000@g.us"
ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "tests" / "fixtures" / "bridge_stub.mjs"


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
    def ponte(self):
        storage = LocalSessionStorage()
        bridge = WhatsAppBridge(storage, script=STUB, timeout=10)
        return storage, bridge

    @staticmethod
    def evento(event_id, texto):
        return {"event_id": event_id, "message_id": message_id(GROUP, event_id), "texto": texto}

    def test_sucesso_inicia_node_stub_confirma_ack_e_persiste_sessao(self):
        storage, bridge = self.ponte()
        evento = self.evento("quiz-offline-1", "Aviso offline")

        resultado = bridge.enviar_lote(GROUP, [evento])

        self.assertEqual(resultado["sessao"], "ok")
        self.assertEqual(resultado["resultados"][0]["ack"], True)
        self.assertEqual(storage.writes[0][0]["creds.json"], '{"client":"offline","stub_used":true}')
        self.assertEqual(storage.writes[0][1], "1")

    def test_sucesso_devolve_somente_contrato_publico(self):
        storage, bridge = self.ponte()
        evento = self.evento("evento-unicode", "Atenção: café às 19h")

        resultado = bridge.enviar_lote(GROUP, [evento])

        self.assertEqual(resultado["resultados"][0]["event_id"], "evento-unicode")
        self.assertEqual(resultado["resultados"][0]["message_id"], evento["message_id"])

    def test_timeout_nao_confirma_nem_persiste_sessao(self):
        storage, bridge = self.ponte()
        evento = self.evento("evento-timeout", "[stub:timeout] Aviso offline")

        resultado = bridge.enviar_lote(GROUP, [evento])

        self.assertEqual(resultado["sessao"], "timeout")
        item = resultado["resultados"][0]
        self.assertIs(item["ack"], False)
        self.assertIs(item["timeout"], True)
        self.assertEqual(storage.writes, [])

    def test_ack_divergente_e_recusado_sem_persistir_sessao(self):
        storage, bridge = self.ponte()
        evento = self.evento("evento-divergente", "[stub:ack-divergente] Aviso offline")

        with self.assertRaises(BridgeError) as contexto:
            bridge.enviar_lote(GROUP, [evento])

        self.assertIn("resposta de sucesso inconsistente", str(contexto.exception))
        self.assertEqual(storage.writes, [])

    def test_crash_do_processo_node_e_recusado_sem_persistir_sessao(self):
        storage, bridge = self.ponte()
        evento = self.evento("evento-crash", "[stub:crash] Aviso offline")

        with self.assertRaises(BridgeError) as contexto:
            bridge.enviar_lote(GROUP, [evento])

        self.assertIn("resposta inválida do processo WhatsApp", str(contexto.exception))
        self.assertEqual(storage.writes, [])


if __name__ == "__main__":
    unittest.main()
