"""Cobertura do runtime dos modos restantes via entrypoint (sem sentinela).

O caminho ``rodada`` é exercitado em processo com o ambiente controlado
(nenhuma variável ``SURICATA_*``): sem ``SURICATA_ESTADO_URI`` a rodada
falha em código 5 (armazenamento) antes de qualquer rede, sessão ou ponte.
"""
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

from suricata import entrypoint


class EntrypointRuntimeTests(unittest.TestCase):
    def _sem_ambiente_suricata(self):
        ambiente = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("SURICATA_")
        }
        return patch.dict(os.environ, ambiente, clear=True)

    def test_rodada_sem_estado_uri_retorna_exit_5_do_runtime(self):
        output = io.StringIO()
        with self._sem_ambiente_suricata(), contextlib.redirect_stdout(output):
            code = entrypoint.main(["--mode", "rodada"])
        self.assertEqual(code, 5)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["estado"], "erro")
        self.assertIn("SURICATA_ESTADO_URI", payload["erro"])

    def test_rodada_dispatch_retorna_codigo_do_runtime(self):
        with self._sem_ambiente_suricata():
            with patch("suricata.rodada.main", return_value=7) as rodada_main:
                self.assertEqual(entrypoint.main(["--mode", "rodada"]), 7)
        rodada_main.assert_called_once_with()

    def test_demo_dispatch_retorna_zero(self):
        output = io.StringIO()
        with self._sem_ambiente_suricata(), contextlib.redirect_stdout(output):
            code = entrypoint.main(["--mode", "demo"])
        self.assertEqual(code, 0)
        self.assertIn("modo demo", output.getvalue())


if __name__ == "__main__":
    unittest.main()
