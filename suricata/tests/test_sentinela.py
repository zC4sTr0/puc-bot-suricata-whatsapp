import unittest
from datetime import datetime, timezone

from suricata.adapter import FakeCanvasAdapter, PublicCollection, PublicResponse
from suricata.sentinela import coletar_candidatos_publicos, executar_rodada_sombra, projetar_para_dominio


NOW = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)


class SentinelaAdapterIntegrationTests(unittest.TestCase):
    def test_adapter_publico_alimenta_decisao_de_quiz_sem_campos_privados(self):
        adapter = FakeCanvasAdapter(
            planner={"status": 200, "items": []},
            assignments={"A": {"status": 200, "items": [{
                "id": 7, "name": "Quiz relâmpago", "quiz_id": 8,
                "unlock_at": "2026-09-13T12:10:00Z", "submission": {"grade": 10},
                "user_id": 99, "access_token": "segredo",
            }]}},
        )

        report = executar_rodada_sombra(adapter, ["A"], NOW)

        self.assertEqual(report["estado"], "concluida")
        self.assertEqual(report["avisos"], 1)
        self.assertEqual(report["decisoes"][0]["decisao"], "alertar")
        self.assertNotIn("submission", repr(report))
        self.assertNotIn("segredo", repr(report))

    def test_adapter_preserva_403_404_e_vazio_sem_inferir_ausencia(self):
        for status in (403, 404):
            with self.subTest(status=status):
                adapter = FakeCanvasAdapter(
                    planner={"status": 200, "items": []},
                    assignments={"A": {"status": status, "items": []}},
                )
                report = executar_rodada_sombra(adapter, ["A"], NOW)
                self.assertEqual(report["estado"], "parcial")
                self.assertEqual(report["avisos"], 0)
                self.assertEqual(report["coleta"]["falhas"][0]["status"], status)

        vazio = FakeCanvasAdapter(
            planner={"status": 200, "items": []},
            assignments={"A": {"status": 200, "items": []}},
        )
        report = executar_rodada_sombra(vazio, ["A"], NOW)
        self.assertEqual(report["estado"], "concluida")
        self.assertEqual(report["projetados"], 0)
        self.assertEqual(report["avisos"], 0)

    def test_oferta_excluida_nao_e_consultada_pelo_adapter(self):
        adapter = FakeCanvasAdapter(
            planner={"status": 200, "items": []},
            assignments={"289837": {"status": 200, "items": [{"id": 1, "name": "não consultar"}]},
                          "A": {"status": 200, "items": []}},
        )

        coletar_candidatos_publicos(adapter, ["289837", "A"])

        self.assertEqual(adapter.calls, [("planner", None), ("assignments", "A")])

    def test_projecao_remove_dados_privados_antes_da_politica(self):
        eventos = projetar_para_dominio([{
            "id": 1, "course_id": "A", "name": "Prova", "submission": {"grade": 10},
            "user_id": 99, "token": "segredo",
        }])
        self.assertEqual(len(eventos), 1)
        self.assertNotIn("submission", repr(eventos[0]))
        self.assertNotIn("segredo", repr(eventos[0]))

    def test_collector_legado_exige_opt_in_explicito(self):
        class Legacy:
            def planner(self):
                return {"status": 200, "items": []}

            def assignments(self, oferta):
                return {"status": 200, "items": [{"id": oferta, "name": "Tarefa"}]}

        self.assertEqual(coletar_candidatos_publicos(Legacy(), ["A"]).estado, "indisponivel")
        self.assertEqual(len(coletar_candidatos_publicos(Legacy(), ["A"], legacy_collector=True).candidatos), 1)

    def test_adapter_com_planner_falho_descarta_assignments_e_nao_projeta(self):
        class Adapter:
            def coletar(self, ofertas):
                return PublicCollection(
                    planner=PublicResponse(status=503),
                    assignments={"A": PublicResponse(status=200, items=({"id": "vazamento"},))},
                )

        coleta = coletar_candidatos_publicos(Adapter(), ["A"])

        self.assertEqual(coleta.planner.status, 503)
        self.assertEqual(coleta.ofertas, {})
        self.assertEqual(coleta.candidatos, [])

    def test_rodada_sombra_permite_legacy_somente_com_flag_explicita(self):
        class Legacy:
            def planner(self):
                return {"status": 200, "items": []}

            def assignments(self, oferta):
                return {"status": 200, "items": [{"id": oferta, "name": "Quiz", "quiz_id": 1}]}

        sem_opt_in = executar_rodada_sombra(Legacy(), ["A"], NOW)
        com_opt_in = executar_rodada_sombra(Legacy(), ["A"], NOW, legacy_collector=True)

        self.assertEqual(sem_opt_in["estado"], "indisponivel")
        self.assertEqual(com_opt_in["projetados"], 1)


if __name__ == "__main__":
    unittest.main()
