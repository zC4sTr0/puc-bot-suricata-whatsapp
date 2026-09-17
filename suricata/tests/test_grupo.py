import unittest
from datetime import datetime, timedelta, timezone

from suricata.grupo import (
    EXCLUIDAS,
    anuncio_relevante,
    decidir_grupo,
    ofertas_elegiveis,
    renderizar_dia_grupo,
    renderizar_evento,
)


class GrupoTests(unittest.TestCase):
    AGORA = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)

    def evento(self, **extra):
        value = {
            "event_id": "evt-1",
            "curso": "Fundamentos de Dados",
            "titulo": "Quiz P2",
            "tipo": "quiz",
            "unlock_at": "2026-09-14T12:10:00+00:00",
            "due_at": "2026-09-15T12:00:00+00:00",
            "pontos": 10,
            "url": "https://canvas.example/assignments/1",
        }
        value.update(extra)
        return value

    def test_ofertas_elegiveis_exclui_as_duas_ofertas_e_os_zeros(self):
        self.assertEqual(
            ofertas_elegiveis({"289837": 4, "104959": 1, "292184": 2, "292185": 0}),
            {"292184"},
        )
        self.assertEqual(EXCLUIDAS, frozenset({"289837", "104959"}))

    def test_entregue_e_estado_aninhado_nao_vazam_para_o_texto(self):
        texto = renderizar_evento(
            self.evento(
                entregue=True,
                estado="atrasado_recuperavel",
                privado={"submission": {"nota": 10, "token": "segredo"}},
            ),
            self.AGORA,
        )
        proibidos = ("situação", "entregue", "atrasad", "perdid", "nota", "token", "segredo")
        for termo in proibidos:
            self.assertNotIn(termo, texto.casefold())
        self.assertIn("QUIZ NOVO", texto)
        self.assertLessEqual(len(texto), 1500)

    def test_quiz_e_avaliacao_sao_alertas_mesmo_sem_prazo_proximo(self):
        self.assertEqual(decidir_grupo(self.evento(due_at=None), self.AGORA), "alertar")
        self.assertEqual(
            decidir_grupo(
                self.evento(tipo="avaliacao", titulo="Prova final", due_at=self.AGORA + timedelta(days=5)),
                self.AGORA,
            ),
            "alertar",
        )

    def test_tarefa_em_ate_48_h_alerta_e_mais_distante_vai_para_diario(self):
        self.assertEqual(
            decidir_grupo(self.evento(tipo="tarefa", due_at=self.AGORA + timedelta(hours=48)), self.AGORA),
            "alertar",
        )
        self.assertEqual(
            decidir_grupo(self.evento(tipo="tarefa", due_at=self.AGORA + timedelta(days=3)), self.AGORA),
            "nova_no_diario",
        )

    def test_anuncio_relevante_ignora_acentos_caixa_e_palavras_parciais(self):
        self.assertTrue(anuncio_relevante("Prova P2 remarcada", "Confira o horário"))
        self.assertTrue(anuncio_relevante("AVALIAÇÃO", "informação"))
        self.assertFalse(anuncio_relevante("Material da aula", "Leitura recomendada"))
        self.assertFalse(anuncio_relevante("aprovação", "sem palavra inteira"))

    def test_diario_e_deterministico_e_segunda_tem_sinal_de_vida(self):
        eventos = [self.evento(event_id="b", titulo="B", tipo="tarefa"), self.evento(event_id="a", titulo="A", tipo="tarefa")]
        primeiro = renderizar_dia_grupo(eventos, self.AGORA)
        segundo = renderizar_dia_grupo(list(reversed(eventos)), self.AGORA)
        self.assertEqual(primeiro, segundo)
        self.assertIn("Hoje, 15/09", primeiro)
        self.assertEqual(renderizar_dia_grupo([], self.AGORA), "")
        segunda = datetime(2026, 9, 14, 7, tzinfo=timezone.utc)
        self.assertIn("Semana 14/09–20/09", renderizar_dia_grupo([], segunda))


if __name__ == "__main__":
    unittest.main()
