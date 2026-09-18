import ast
import contextlib
import io
import json
import unittest
from pathlib import Path

from suricata import entrypoint

ROOT = Path(__file__).resolve().parents[1]


class EntrypointTests(unittest.TestCase):
    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = entrypoint.main(args)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        return code, json.loads(lines[0]), lines[0]

    def test_shadow_emite_json_minimo(self):
        code, record, _ = self.invoke("--mode", "shadow")
        self.assertEqual(code, 0)
        self.assertEqual(record, {"mode": "shadow", "status": "ok", "adapter": "none"})

    def test_config_e_rejeitado_como_argumento_invalido(self):
        code, record, line = self.invoke("--mode", "shadow", "--config", "segredo.json")
        self.assertEqual(code, 2)
        self.assertEqual(record["error"], "argumentos inválidos (use --mode MODO; veja --help)")
        self.assertNotIn("segredo.json", line)

    def test_modo_invalido_falha_sem_detalhes(self):
        code, record, line = self.invoke("--mode", "modo-inexistente")
        self.assertEqual(code, 2)
        self.assertEqual(record["error"], "modo inválido (veja --help)")
        self.assertNotIn("modo-inexistente", line)

    def test_modos_removidos_sao_invalidos(self):
        for modo in ("sentinela", "grupos", "teste-envio"):
            with self.subTest(modo=modo):
                code, record, _ = self.invoke("--mode", modo)
                self.assertEqual(code, 2)
                self.assertEqual(record["error"], "modo inválido (veja --help)")

    def test_modo_ausente(self):
        code, record, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(record["error"], "modo ausente (veja --help)")

    def test_entrypoint_nao_importa_rede_subprocesso_ou_segredos(self):
        tree = ast.parse((ROOT / "entrypoint.py").read_text(encoding="utf-8"))
        forbidden = {"subprocess", "socket", "ssl", "urllib", "http", "requests", "secrets", "boto3"}
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertTrue(imported.isdisjoint(forbidden), imported & forbidden)


if __name__ == "__main__":
    unittest.main()
