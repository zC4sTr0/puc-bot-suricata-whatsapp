import unittest
from datetime import datetime, timedelta, timezone

from suricata.domain import (
    DomainError,
    anuncio_relevante,
    decidir_grupo,
    normalizar_evento,
    ofertas_elegiveis,
    renderizar_publico,
)


class DomainTests(unittest.TestCase):
    MOMENTO = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)

    def evento(self, **extra):
        value = {
            "event_id": "a-1",
            "curso": "Fundamentos de Dados",
            "titulo": "Quiz P2",
            "tipo": "quiz",
            "unlock_at": "2026-09-13T12:10:00+00:00",
            "lock_at": "2026-09-14T12:00:00+00:00",
            "pontos": 10,
            "url": "https://canvas.example/assignments/1",
        }
        value.update(extra)
        return value

    def test_normaliza_tipos_e_datas_sem_mutar_entrada(self):
        raw = self.evento(tipo="QUIZ", pontos="10", titulo="  Quiz P2  ")
        normalized = normalizar_evento(raw)
        self.assertEqual(normalized.tipo, "quiz")
        self.assertEqual(normalized.pontos, 10.0)
        self.assertEqual(normalized.titulo, "Quiz P2")
        self.assertEqual(raw["titulo"], "  Quiz P2  ")

    def test_fronteira_rejeita_campos_pessoais_e_proibidos(self):
        for field in ("submission", "entrega", "atraso", "nota", "situação"):
            with self.subTest(field=field):
                with self.assertRaises(DomainError):
                    normalizar_evento(self.evento(**{field: "privado"}))

    def test_elegibilidade_exclui_ofertas_e_zeros(self):
        self.assertEqual(ofertas_elegiveis({"289837": 2, "104959": 1, "A": 1, "B": 0}), {"A"})

    def test_decisao_preserva_quiz_sem_prazo_e_avaliacao_distante(self):
        self.assertEqual(decidir_grupo(self.evento(lock_at=None, due_at=None), self.MOMENTO), "alertar")
        self.assertEqual(
            decidir_grupo(self.evento(tipo="avaliacao", titulo="Prova final", lock_at=None, due_at=self.MOMENTO + timedelta(days=5)), self.MOMENTO),
            "alertar",
        )

    def test_item_entregue_continua_alertavel(self):
        self.assertEqual(decidir_grupo(self.evento(entregue=True), self.MOMENTO), "alertar")

    def test_tarefa_curta_alerta_e_distante_vai_para_diario(self):
        self.assertEqual(decidir_grupo(self.evento(tipo="tarefa", lock_at=self.MOMENTO + timedelta(hours=48)), self.MOMENTO), "alertar")
        self.assertEqual(decidir_grupo(self.evento(tipo="tarefa", lock_at=self.MOMENTO + timedelta(days=3)), self.MOMENTO), "nova_no_diario")

    def test_anuncio_relevante_ignora_acentos_e_caixa(self):
        self.assertTrue(anuncio_relevante("Prova P2 remarcada", "Confira o novo horário"))
        self.assertTrue(anuncio_relevante("AVALIAÇÃO", "informação"))
        self.assertFalse(anuncio_relevante("Material da aula", "Leitura recomendada"))
        self.assertFalse(anuncio_relevante("aprovação", "sem palavra inteira"))

    def test_renderizacao_publica_remove_variantes_flexionadas_de_estado_pessoal(self):
        text = renderizar_publico(
            self.evento(
                curso="Notas atrasos e entregas",
                titulo="Submissions atrasadas e situações perdidas",
                url="https://example.test/notas-entregas",
            )
        )
        lowered = text.casefold()
        for forbidden in (
            "nota",
            "atraso",
            "entrega",
            "submission",
            "situação",
            "perdida",
        ):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("QUIZ NOVO", text)

    def test_renderizacao_publica_tem_limite_e_nunca_expoe_estado_pessoal(self):
        text = renderizar_publico(self.evento(entregue=True, estado="atrasado_recuperavel"))
        self.assertLessEqual(len(text), 1500)
        lowered = text.casefold()
        for forbidden in ("situação", "entregue", "atrasad", "perdid", "nota", "submission", "entrega"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("QUIZ NOVO", text)
    def test_renderizacao_publica_remove_controles_ansi_e_quebras_injetadas(self):
        text = renderizar_publico(
            self.evento(
                curso="Dados \x1b[31mvermelhos\x1b[0m\r\nFORJADO: curso",
                titulo="Quiz P2\r\nFORJADO: aprovado\x1b[2J",
                url="https://example.test/a\nFORJADO: https://evil.test",
            )
        )

        self.assertEqual(text.count("\n"), 4)
        for line in text.splitlines():
            self.assertNotRegex(line, r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
        self.assertNotIn("\x1b", text)
        self.assertTrue(all(not line.startswith("FORJADO") for line in text.splitlines()))
        self.assertIn("Dados vermelhosFORJADO: curso", text)
        self.assertIn("Quiz P2FORJADO: aprovado", text)
        self.assertIn("https://example.test/aFORJADO: https://evil.test", text)


if __name__ == "__main__":
    unittest.main()
