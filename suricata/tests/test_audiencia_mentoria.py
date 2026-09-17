"""Regressão da audiência: Mentoria de Carreira é monitorada."""
from __future__ import annotations

import unittest

from suricata.rodada import coletar
from suricata.tests.test_rodada import AGORA, CanvasFalso, quiz


class AudienciaMentoriaTests(unittest.TestCase):
    def test_coleta_assignment_de_mentoria(self):
        canvas = CanvasFalso()
        canvas.assignments["289837"] = [
            quiz(41, abre=AGORA, fecha=AGORA),
        ]

        coleta = coletar(canvas.cliente(), AGORA)

        self.assertEqual([a.curso_id for a in coleta.atividades], ["289837"])
        self.assertTrue(any("/courses/289837/assignments" in url for url in canvas.urls))


if __name__ == "__main__":
    unittest.main()
