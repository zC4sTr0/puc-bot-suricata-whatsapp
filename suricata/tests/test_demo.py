"""Contrato do modo demo: rodada offline, zero-config, sem efeito externo (T3.4).

Um estudante roda ``python -m suricata --mode demo`` SEM nenhuma variável
``SURICATA_*`` e deve ver as mensagens planejadas + o relatório da rodada +
uma linha deixando claro que a entrega está desligada. Exit 0.

O subprocesso é real e o ambiente é hostil de propósito:

- ``PATH`` vazio: tripwire — qualquer spawn de node falharia alto;
- ``TMPDIR``/``TEMP``/``TMP`` apontando para um diretório temporário: todo
  estado (ObjetosLocais, outbox temporário) tem que nascer e morrer ali;
- o conjunto de arquivos do repo é fotografado antes e depois: o demo não
  pode escrever nada fora do temporário;
- duas execuções têm que produzir byte a byte o mesmo stdout: o relógio é
  fixo dentro do demo e as datas da fixture são coerentes com ele.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # raiz do repo (contém o pacote suricata/)


def _arquivos_do_repo() -> set[str]:
    return {
        str(caminho.relative_to(ROOT))
        for caminho in ROOT.rglob("*")
        if caminho.is_file() and ".git" not in caminho.parts
    }


class ModoDemoTests(unittest.TestCase):
    def _rodar_demo(self, pasta_tmp: str) -> subprocess.CompletedProcess:
        ambiente = {
            chave: valor
            for chave, valor in os.environ.items()
            if not chave.upper().startswith("SURICATA_")
        }
        ambiente.update({
            "PATH": "",  # tripwire: nenhum binário externo pode ser spawnado
            "TMPDIR": pasta_tmp,
            "TEMP": pasta_tmp,
            "TMP": pasta_tmp,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        return subprocess.run(
            [sys.executable, "-m", "suricata", "--mode", "demo"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=ambiente,
            timeout=120,
        )

    def test_demo_zero_config_offline_deterministico_sem_escrita_no_repo(self):
        antes = _arquivos_do_repo()
        with tempfile.TemporaryDirectory() as pasta_tmp:
            primeira = self._rodar_demo(pasta_tmp)
            segunda = self._rodar_demo(pasta_tmp)
        depois = _arquivos_do_repo()

        # (b) exit 0, sem nada em stderr.
        self.assertEqual(primeira.returncode, 0, primeira.stderr)
        self.assertEqual(primeira.stderr, "")
        # (c) stdout traz os textos de mensagens planejadas da fixture congelada:
        # a lista e a prova de amanhã descobertas às 18:00 e o quiz-relâmpago de hoje.
        self.assertIn("entrega amanhã no Canvas", primeira.stdout)
        self.assertIn("prova amanhã no Canvas", primeira.stdout)
        self.assertIn("quiz hoje no Canvas", primeira.stdout)
        # A rodada exibida não é linha de base: os avisos são novidade dela.
        self.assertIn('"linha_de_base": false', primeira.stdout)
        # O relatório da rodada também vai ao stdout, e em modo sombra.
        self.assertIn('"modo": "sombra"', primeira.stdout)
        # (d) linha explícita de entrega desligada.
        self.assertIn("entrega: desligada", primeira.stdout)
        # (e) nenhum arquivo escrito fora do diretório temporário.
        self.assertEqual(depois - antes, set(), "o demo escreveu arquivo no repo")
        # (f) saída estável entre duas execuções (relógio fixo + fixture congelada).
        self.assertEqual(primeira.stdout, segunda.stdout)


if __name__ == "__main__":
    unittest.main()
