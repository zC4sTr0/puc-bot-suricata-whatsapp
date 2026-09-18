import ast
import builtins
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from suricata import entrypoint

ROOT = Path(__file__).resolve().parents[1]


class FakeCanvasClient:
    def __init__(self, *, status=200, items=None, **kwargs):
        self.status = status
        self.items = items or []
        self.kwargs = kwargs
        self.calls = []

    def assignments(self, oferta):
        self.calls.append(oferta)
        return type("Response", (), {"status": self.status, "items": self.items})()


class EntrypointTests(unittest.TestCase):
    def invoke(self, *args, client_factory=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = entrypoint.main(args, client_factory=client_factory or FakeCanvasClient)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        return code, json.loads(lines[0]), lines[0]

    def config_file(self, directory, value):
        path = Path(directory) / "config.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_shadow_emite_json_minimo(self):
        code, record, _ = self.invoke("--mode", "shadow")
        self.assertEqual(code, 0)
        self.assertEqual(record, {"mode": "shadow", "status": "ok", "adapter": "none"})

    def test_shadow_nao_abre_configuracao(self):
        with patch.object(builtins, "open", side_effect=AssertionError("shadow abriu arquivo")):
            code, record, _ = self.invoke("--mode", "shadow", "--config", "segredo.json")
        self.assertEqual(code, 0)
        self.assertEqual(record["status"], "ok")

    def test_modo_invalido_falha_sem_detalhes(self):
        code, record, line = self.invoke("--mode", "modo-inexistente")
        self.assertEqual(code, 2)
        self.assertEqual(record["error"], "modo inválido (veja --help)")
        self.assertNotIn("modo-inexistente", line)

    def test_sentinela_exige_configuracao_e_ofertas(self):
        code, record, _ = self.invoke("--mode", "sentinela")
        self.assertEqual(code, 2)
        self.assertEqual(record["error"], "configuração ausente (use --config com um JSON como suricata/config.example.json)")
        with tempfile.TemporaryDirectory() as directory:
            path = self.config_file(directory, {"ambiente": "teste"})
            code, record, _ = self.invoke("--mode", "sentinela", "--config", str(path))
        self.assertEqual(code, 2)
        self.assertEqual(record["error"], "configuração inválida")

    def test_config_rejeita_origin_externa_ou_com_path(self):
        for origin in ("https://evil.example", "https://pucminas.instructure.com/api/v1"):
            with self.subTest(origin=origin), tempfile.TemporaryDirectory() as directory:
                path = self.config_file(directory, {"ofertas": ["A"], "canvas": {"origin": origin}})
                code, record, line = self.invoke("--mode", "sentinela", "--config", str(path))
            self.assertEqual(code, 2)
            self.assertEqual(record["error"], "configuração inválida")
            self.assertNotIn(origin, line)

    def test_config_rejeita_timeout_nao_finito(self):
        for timeout in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as directory:
                path = self.config_file(directory, {"ofertas": ["A"], "canvas": {"timeout": timeout}})
                code, record, line = self.invoke("--mode", "sentinela", "--config", str(path))
            self.assertEqual(code, 2)
            self.assertEqual(record["error"], "configuração inválida")
            self.assertNotIn("nan", line.casefold())
            self.assertNotIn("inf", line.casefold())

    def test_config_minima_valida_constroi_cliente_e_emite_relatorio(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.config_file(directory, {"ofertas": ["A"]})
            made = []

            def factory(**kwargs):
                client = FakeCanvasClient(items=[{"id": 7, "name": "Tarefa", "course_id": "A"}], **kwargs)
                made.append(client)
                return client

            code, record, line = self.invoke("--mode", "sentinela", "--config", str(path), client_factory=factory)
        self.assertEqual(code, 0)
        self.assertEqual(record["mode"], "sentinela")
        self.assertEqual(record["relatorio"]["coleta"]["assignments"], 1)
        self.assertEqual(made[0].calls, ["A"])
        self.assertNotIn("token", line.casefold())

    def test_canvas_indisponivel_e_403_mantem_relatorio_honesto(self):
        for status, estado in ((None, "indisponivel"), (403, "acesso_negado")):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                path = self.config_file(directory, {"ofertas": ["A"]})
                factory = lambda **kwargs: FakeCanvasClient(status=status, **kwargs)
                code, record, _ = self.invoke("--mode", "sentinela", "--config", str(path), client_factory=factory)
            self.assertEqual(code, 0)
            self.assertEqual(record["relatorio"]["coleta"]["falhas"][0]["estado"], estado)
            self.assertEqual(record["relatorio"]["avisos"], 0)

    def test_ausencia_de_token_nao_bloqueia_nem_vaza_segredo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.config_file(directory, {"ofertas": ["A"]})
            received = []

            def factory(**kwargs):
                received.append(kwargs)
                return FakeCanvasClient(**kwargs)

            code, record, line = self.invoke("--mode", "sentinela", "--config", str(path), client_factory=factory)
        self.assertEqual(code, 0)
        self.assertNotIn("token", received[0])
        self.assertNotIn("token", line.casefold())
        self.assertEqual(record["relatorio"]["envio_whatsapp"], "desabilitado")

    def test_erro_sanitizado_nao_exibe_path_ou_payload(self):
        path = "/tmp/canvas-token-super-secreto.json"
        code, record, line = self.invoke("--mode", "sentinela", "--config", path)
        self.assertEqual(code, 2)
        self.assertEqual(record["error"], "configuração inválida")
        self.assertNotIn(path, line)
        self.assertNotIn("super-secreto", line)

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
