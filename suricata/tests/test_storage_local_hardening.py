import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from suricata.rodada.agenda_manual import complementar
from suricata.storage.gcs import ObjetosLocais


class AgendaManualHardeningTests(unittest.TestCase):
    def test_pontos_manualmente_aceitam_apenas_finitos_nao_negativos(self):
        base = {
            "curso_id": "curso-1",
            "tipo": "tarefa",
            "data": "2026-09-20",
            "titulo": "Atividade",
        }
        atividades = [
            complementar([], [{**base, "id": str(i), "pontos": pontos}])
            for i, pontos in enumerate((0, 2, 2.5, -1, float("nan"), float("inf"), float("-inf")))
        ]

        self.assertEqual([item[0].pontos if item else None for item in atividades], [0.0, 2.0, 2.5, None, None, None, None])


class ObjetosLocaisHardeningTests(unittest.TestCase):
    def test_falha_antes_da_troca_final_preserva_snapshot_anterior(self):
        with tempfile.TemporaryDirectory() as pasta:
            objetos = ObjetosLocais(Path(pasta))
            primeira = objetos.gravar("estado.json", b'{"versao":1}', generation=None)

            real_replace = __import__("os").replace
            chamadas = 0

            def falhar_na_troca_final(origem, destino):
                nonlocal chamadas
                chamadas += 1
                if chamadas == 2:
                    raise OSError("falha simulada antes da troca final")
                return real_replace(origem, destino)

            with patch("suricata.storage.gcs.os.replace", side_effect=falhar_na_troca_final):
                with self.assertRaises(OSError):
                    objetos.gravar("estado.json", b'{"versao":2}', generation=primeira)

            snapshot = objetos.ler("estado.json")
            self.assertEqual(snapshot.dados, b'{"versao":1}')
            self.assertEqual(snapshot.generation, primeira)
            self.assertEqual(list(Path(pasta).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
