import unittest

from suricata.adapter import (
    CanvasPublicAdapter,
    FakeCanvasAdapter,
    PublicResponse,
    unavailable_planner,
)


class AdapterTests(unittest.TestCase):
    def test_fake_expõe_respostas_com_status_e_mapeamentos_deterministicos(self):
        adapter = FakeCanvasAdapter(
            planner={"status": 200, "items": [{"id": "planner-2"}, {"id": "planner-1"}]},
            assignments={
                "course-1": {
                    "status": 200,
                    "items": [
                        {"id": 2, "name": "B", "due_at": None},
                        {"id": 1, "name": "A", "points_possible": 10},
                    ],
                }
            },
        )

        self.assertEqual(
            adapter.planner_publico(),
            PublicResponse(status=200, items=({"id": "planner-1"}, {"id": "planner-2"})),
        )
        self.assertEqual(
            adapter.assignments_publicos("course-1"),
            PublicResponse(
                status=200,
                items=(
                    {"id": "1", "name": "A", "points_possible": 10.0},
                    {"id": "2", "name": "B"},
                ),
            ),
        )

    def test_adapter_remove_campos_de_submission_e_identidade(self):
        adapter = FakeCanvasAdapter(
            assignments={
                "course-1": {
                    "status": 200,
                    "items": [{
                        "id": 3,
                        "name": "Quiz",
                        "submission": {"grade": 10},
                        "user_id": 99,
                        "access_token": "secret",
                    }],
                }
            }
        )

        result = adapter.assignments_publicos("course-1")

        self.assertEqual(result.items, ({"id": "3", "name": "Quiz"},))
        self.assertNotIn("submission", repr(result))
        self.assertNotIn("user_id", repr(result))
        self.assertNotIn("secret", repr(result))

    def test_adapter_rejeita_segredos_aninhados_sem_stringificar_payload(self):
        for private_field in ("token", "session", "submission", "identity"):
            with self.subTest(private_field=private_field):
                adapter = FakeCanvasAdapter(
                    assignments={
                        "course-1": {
                            "status": 200,
                            "items": [{
                                "id": 3,
                                "name": "Quiz",
                                "description": {private_field: "secret"},
                            }],
                        }
                    }
                )

                result = adapter.assignments_publicos("course-1")

                self.assertEqual(result.status, 200)
                self.assertEqual(result.items, ())
                self.assertEqual(result.error, "invalid_payload")
                self.assertNotIn("secret", repr(result))

    def test_adapter_rejeita_segredo_aninhado_dentro_de_lista(self):
        adapter = FakeCanvasAdapter(
            assignments={
                "course-1": {
                    "status": 200,
                    "items": [{
                        "id": 3,
                        "name": "Quiz",
                        "description": [{"identity": "student-secret"}],
                    }],
                }
            }
        )

        result = adapter.assignments_publicos("course-1")

        self.assertEqual(result.status, 200)
        self.assertEqual(result.items, ())
        self.assertEqual(result.error, "invalid_payload")
        self.assertNotIn("student-secret", repr(result))

    def test_adapter_preserva_apenas_escalar_publico_com_normalizacao_deterministica(self):
        adapter = FakeCanvasAdapter(
            assignments={
                "course-1": {
                    "status": 200,
                    "items": [{
                        "id": 3,
                        "name": " <b>Quiz</b> ",
                        "description": " <p>Instruções</p> ",
                        "points_possible": 10,
                    }],
                }
            }
        )

        result = adapter.assignments_publicos("course-1")

        self.assertEqual(
            result.items,
            ({"description": "Instruções", "id": "3", "name": "Quiz", "points_possible": 10.0},),
        )

    def test_planner_indisponivel_interrompe_coleta_sem_consultar_assignments(self):
        adapter = FakeCanvasAdapter(planner=unavailable_planner())

        result = adapter.coletar(["course-1"])

        self.assertEqual(result.planner.status, None)
        self.assertEqual(result.planner.error, "planner_unavailable")
        self.assertEqual(result.assignments, {})
        self.assertEqual(adapter.calls, [("planner", None)])
        self.assertFalse(result.usavel)

    def test_status_nao_ok_do_planner_tambem_e_fail_closed(self):
        adapter = FakeCanvasAdapter(planner={"status": 503, "items": []})

        result = adapter.coletar(["course-1"])

        self.assertEqual(result.planner.status, 503)
        self.assertEqual(result.assignments, {})
        self.assertEqual(adapter.calls, [("planner", None)])
        self.assertFalse(result.usavel)

    def test_planner_ok_coleta_assignments_e_preserva_status_de_cada_oferta(self):
        adapter = FakeCanvasAdapter(
            planner={"status": 200, "items": []},
            assignments={
                "course-2": {"status": 403, "items": []},
                "course-1": {"status": 200, "items": [{"id": 7, "name": "A"}]},
            },
        )

        result = adapter.coletar(["course-2", "course-1"])

        self.assertEqual(tuple(result.assignments), ("course-1", "course-2"))
        self.assertEqual(result.assignments["course-1"].items, ({"id": "7", "name": "A"},))
        self.assertEqual(result.assignments["course-2"].status, 403)
        self.assertFalse(result.usavel)

    def test_adapter_de_canvasclient_usa_somente_interface_existente(self):
        class Client:
            def assignments(self, course_id):
                return type("Response", (), {
                    "status": 200,
                    "items": (type("Assignment", (), {"id": 8, "name": "Tarefa", "points_possible": None,
                                                        "description": "", "due_at": None, "unlock_at": None,
                                                        "lock_at": None, "quiz_id": None})(),),
                })()

        adapter = CanvasPublicAdapter(Client())
        self.assertEqual(adapter.assignments_publicos("course-1").items, ({"id": "8", "name": "Tarefa"},))


if __name__ == "__main__":
    unittest.main()
