import unittest
from datetime import datetime, timezone

from suricata.application import SentinelaApplication, executar_sombra
from suricata.sentinela import Coleta, coletar_candidatos_publicos


NOW = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)


class FakeCanvas:
    def __init__(self, planner, assignments, statuses=None):
        self.planner = planner
        self.assignments = assignments
        self.statuses = statuses or {}
        self.calls = []

    def planner_publico(self):
        self.calls.append(("planner", None))
        return self.planner

    def assignments_publicos(self, oferta):
        self.calls.append(("assignments", str(oferta)))
        status = self.statuses.get(str(oferta), 200)
        if status != 200:
            return {"status": status, "items": []}
        return {"status": 200, "items": self.assignments.get(str(oferta), [])}


class ShadowRuntimeTests(unittest.TestCase):
    def test_quiz_sem_prazo_e_encontrado_na_varredura_e_decidido(self):
        canvas = FakeCanvas(
            {"status": 200, "items": []},
            {"A": [{"id": 7, "course_id": "A", "name": "Quiz sem prazo", "quiz_id": 8,
                    "unlock_at": "2026-09-13T12:10:00Z", "due_at": None, "lock_at": None}]},
        )
        report = executar_sombra(canvas, ofertas=["A"], momento=NOW)
        self.assertEqual(report["estado"], "concluida")
        self.assertEqual(report["decisoes"], [{"event_id": "canvas:pucminas:course:A:assignment:7", "decisao": "alertar"}])
        self.assertEqual(report["avisos"], 1)

    def test_oferta_excluida_nunca_e_consultada(self):
        canvas = FakeCanvas({"status": 200, "items": []}, {"289837": [{"id": 1}]})
        report = executar_sombra(canvas, ofertas=["289837", "A"], momento=NOW)
        self.assertNotIn(("assignments", "289837"), canvas.calls)
        self.assertEqual(report["coleta"]["ofertas_consultadas"], 1)

    def test_resposta_parcial_nao_anuncia_ausencia(self):
        canvas = FakeCanvas({"status": 200, "items": []}, {"A": [], "B": []}, {"B": 500})
        report = executar_sombra(canvas, ofertas=["A", "B"], momento=NOW)
        self.assertEqual(report["estado"], "parcial")
        self.assertEqual(report["avisos"], 0)
        self.assertNotIn("ausente", report)
        self.assertEqual(report["coleta"]["falhas"][0]["estado"], "erro")

    def test_falha_total_e_fail_closed_sem_decisao_ou_aviso(self):
        canvas = FakeCanvas({"status": 500, "items": []}, {}, {"A": 500})
        report = executar_sombra(canvas, ofertas=["A"], momento=NOW)
        self.assertEqual(report["estado"], "indisponivel")
        self.assertEqual(report["decisoes"], [])
        self.assertEqual(report["avisos"], 0)
        self.assertEqual(report["coleta"]["planner"]["estado"], "erro")

    def test_canvas_ausente_403_404_e_500_mantem_estado_honesto(self):
        for status, estado in ((None, "indisponivel"), (403, "acesso_negado"),
                               (404, "ausente"), (500, "erro")):
            with self.subTest(status=status):
                canvas = FakeCanvas({"status": status, "items": []}, {}, {"A": status})
                report = executar_sombra(canvas, ofertas=["A"], momento=NOW)
                self.assertEqual(report["estado"], "indisponivel")
                self.assertEqual(report["coleta"]["planner"]["estado"], estado)
                self.assertEqual(report["avisos"], 0)
                self.assertNotIn("ausencia", " ".join(report["eventos"]))

    def test_sombra_nao_chama_notificador_nem_escreve_por_padrao(self):
        calls = []
        canvas = FakeCanvas({"status": 200, "items": []}, {"A": []})
        app = SentinelaApplication(canvas=canvas, notifier=lambda _: calls.append(1), clock=lambda: NOW)
        app.run(ofertas=["A"])
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
