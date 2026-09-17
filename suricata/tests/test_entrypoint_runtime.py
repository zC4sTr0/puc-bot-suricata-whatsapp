import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from suricata import entrypoint
from suricata.adapter import PublicCollection, PublicResponse


class FakeReadOnlyAdapter:
    def __init__(self, planner=200, assignments=None):
        self.planner = planner
        self.assignments = assignments or {}
        self.calls = []

    def coletar(self, ofertas):
        ofertas = tuple(ofertas)
        self.calls.append(ofertas)
        planner = PublicResponse(self.planner, ({"id": "planner"},) if self.planner == 200 else ())
        responses = {
            oferta: PublicResponse(200, tuple(self.assignments.get(oferta, ())))
            for oferta in ofertas
        }
        return PublicCollection(planner, responses)


class EntrypointRuntimeTests(unittest.TestCase):
    def invoke(self, config, factory):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = entrypoint.main(("--mode", "sentinela", "--config", str(path)), client_factory=factory)
            return code, json.loads(output.getvalue())

    def test_adapter_collection_mapeia_quiz_publico_sem_segredos(self):
        adapter = FakeReadOnlyAdapter(assignments={"oferta-a": ({
            "id": "assignment-7", "name": "Quiz relâmpago", "quiz_id": "quiz-8",
            "unlock_at": "2026-09-14T12:00:00Z",
        },)})
        code, record = self.invoke({"ofertas": ["oferta-a"]}, lambda **_: adapter)
        self.assertEqual(code, 0)
        report = record["relatorio"]
        self.assertEqual(report["coleta"]["assignments"], 1)
        self.assertEqual(report["projetados"], 1)
        self.assertEqual(report["decisoes"][0]["event_id"], "canvas:pucminas:course:oferta-a:assignment:assignment-7")
        self.assertEqual(adapter.calls, [("oferta-a",)])
        self.assertNotIn("token", json.dumps(record).casefold())

    def test_planner_indisponivel_e_fail_closed(self):
        adapter = FakeReadOnlyAdapter(planner=503, assignments={"A": ({"id": "vazamento"},)})
        code, record = self.invoke({"ofertas": ["A"]}, lambda **_: adapter)
        self.assertEqual(code, 0)
        report = record["relatorio"]
        self.assertEqual(report["estado"], "indisponivel")
        self.assertEqual(report["coleta"]["assignments"], 0)
        self.assertEqual(report["projetados"], 0)
        self.assertEqual(report["avisos"], 0)

    def test_state_writer_so_e_criado_com_path_explicito(self):
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "estado"
            adapter = FakeReadOnlyAdapter()
            config = {"ofertas": ["A"], "estado": {"path": str(state_path)}}
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = entrypoint.main(("--mode", "sentinela", "--config", str(path)), client_factory=lambda **_: adapter)
            self.assertEqual(code, 0)
            self.assertTrue((state_path / "heartbeat.json").exists())

    def test_cliente_recebe_somente_timeout_e_origin_sem_token(self):
        received = []

        class Client:
            def __init__(self, **kwargs):
                received.append(kwargs)

            def assignments(self, _oferta):
                raise AssertionError("planner deve bloquear o cliente sem adapter")

        code, record = self.invoke({"ofertas": ["A"], "canvas": {"timeout": 4}}, Client)
        self.assertEqual(code, 0)
        self.assertEqual(received, [{"timeout": 4.0}])
        self.assertEqual(record["relatorio"]["estado"], "parcial")


if __name__ == "__main__":
    unittest.main()
