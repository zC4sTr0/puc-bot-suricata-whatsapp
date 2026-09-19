"""Configuração externa das ofertas Canvas excluídas da coleta."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from suricata.rodada.coleta import coletar
from suricata.rodada.config import cursos_excluidos_do_ambiente
from suricata.tests._fakes import AGORA, CanvasFalso


class CursosExcluidosConfigTests(unittest.TestCase):
    def test_ausente_preserva_oferta_excluida_atual(self):
        self.assertEqual(cursos_excluidos_do_ambiente({}), frozenset({"104959"}))

    def test_lista_comma_separada_aceita_espacos(self):
        self.assertEqual(
            cursos_excluidos_do_ambiente({"SURICATA_CURSOS_EXCLUIDOS": "104959, 100001"}),
            frozenset({"104959", "100001"}),
        )

    def test_rejeita_id_nao_numerico(self):
        with self.assertRaisesRegex(ValueError, "IDs numéricos"):
            cursos_excluidos_do_ambiente({"SURICATA_CURSOS_EXCLUIDOS": "104959,abc"})

    def test_rejeita_item_vazio(self):
        with self.assertRaisesRegex(ValueError, "lista"):
            cursos_excluidos_do_ambiente({"SURICATA_CURSOS_EXCLUIDOS": "104959,"})

    def test_rejeita_duplicata(self):
        with self.assertRaisesRegex(ValueError, "duplicados"):
            cursos_excluidos_do_ambiente({"SURICATA_CURSOS_EXCLUIDOS": "104959, 104959"})

    def test_coleta_usa_exclusoes_configuradas(self):
        canvas = CanvasFalso()
        coletar(canvas.cliente(), AGORA, cursos_excluidos={"104959", "100002"})
        self.assertFalse(any("/courses/104959/" in url or "/courses/100002/" in url for url in canvas.urls))

    def test_coleta_le_a_env_quando_nao_recebe_override(self):
        canvas = CanvasFalso()
        with patch.dict("os.environ", {"SURICATA_CURSOS_EXCLUIDOS": "104959,100002"}):
            coletar(canvas.cliente(), AGORA)
        self.assertFalse(any("/courses/104959/" in url or "/courses/100002/" in url for url in canvas.urls))


if __name__ == "__main__":
    unittest.main()
