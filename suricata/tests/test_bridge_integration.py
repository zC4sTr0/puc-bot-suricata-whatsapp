import unittest

from suricata.dominio.message_id import message_id
from suricata.integracao.bridge import BridgeError, WhatsAppBridge

GROUP = "120363000000000000@g.us"


class BridgeIntegrationTests(unittest.TestCase):
    """Cobertura da ponte com fakes locais: nenhum Node real é iniciado."""

    def test_bridge_rejeita_event_id_duplicado_antes_de_tocar_runner(self):
        storage = type("Storage", (), {})()

        def runner(*_args, **_kwargs):
            self.fail("runner não deveria ser chamado")

        evento = {
            "event_id": "duplicado",
            "message_id": message_id(GROUP, "duplicado"),
            "texto": "aviso",
        }

        with self.assertRaises(BridgeError):
            WhatsAppBridge(storage, run=runner).enviar_lote(GROUP, [evento, dict(evento)])


if __name__ == "__main__":
    unittest.main()
