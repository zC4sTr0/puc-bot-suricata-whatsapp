import unittest
from datetime import datetime, timezone

from suricata.config import Destino
from suricata.horario import BRASILIA
from suricata.publico import BRASILIA as PUBLICO_BRASILIA


class TimeBoundaryCompatibilityTests(unittest.TestCase):
    def test_brasilia_timezone_has_one_canonical_identity(self):
        self.assertIs(PUBLICO_BRASILIA, BRASILIA)

    def test_destination_window_uses_canonical_brasilia_timezone(self):
        destino = Destino("janela", "120363123@g.us", "destinos/janela", "07:00")
        momento = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
        self.assertTrue(destino.elegivel(momento))


if __name__ == "__main__":
    unittest.main()
