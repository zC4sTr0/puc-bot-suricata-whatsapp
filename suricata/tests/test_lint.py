"""Guard de lint: ``ruff check .`` verde na raiz do repo.

O ruff é ferramenta de DEV (não entra nas dependências de runtime). Localmente
ele pode estar disponível como ``ruff`` no PATH ou apenas como módulo
(``python -m ruff``); o CI o instala explicitamente. Sem ruff em lugar nenhum,
o teste faz SKIP com mensagem — nunca falha por ambiente.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from shutil import which

ROOT = Path(__file__).resolve().parents[2]


def _comando_ruff() -> list[str] | None:
    if which("ruff"):
        return ["ruff", "check", "."]
    if which("python") or True:
        try:
            probe = subprocess.run(
                [sys.executable, "-m", "ruff", "--version"],
                capture_output=True, check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if probe.returncode == 0:
                return [sys.executable, "-m", "ruff", "check", "."]
        except (OSError, subprocess.CalledProcessError):
            return None
    return None


class LintTests(unittest.TestCase):
    def test_ruff_check_verde_na_raiz(self):
        comando = _comando_ruff()
        if comando is None:
            self.skipTest("ruff ausente neste ambiente (o CI o instala; veja CONTRIBUTING.md)")
        concluido = subprocess.run(
            comando, cwd=ROOT, capture_output=True, text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
        )
        self.assertEqual(
            concluido.returncode, 0,
            f"ruff encontrou problemas:\n{concluido.stdout}\n{concluido.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
