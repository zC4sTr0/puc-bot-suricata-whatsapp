import unittest

import suricata.config as config
import suricata.configuracao as legacy


class ConfigCompatibilityTests(unittest.TestCase):
    def test_legacy_configuration_facade_reexports_canonical_types_and_parser(self):
        self.assertIs(legacy.Destino, config.Destino)
        self.assertIs(legacy.destinos_do_ambiente, config.destinos_do_ambiente)

    def test_canonical_configuration_preserves_all_destination_contracts(self):
        self.assertEqual(
            [destino.prefixo for destino in config.destinos_do_ambiente({})],
            ["grupo"],
        )
        self.assertEqual(
            [destino.prefixo for destino in config.destinos_do_ambiente({
                "SURICATA_DESTINOS_JSON": '[{"id":"trabalho","jid":"120363123@g.us"}]',
            })],
            ["destinos/trabalho"],
        )


if __name__ == "__main__":
    unittest.main()
