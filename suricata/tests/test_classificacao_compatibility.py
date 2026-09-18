import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import suricata.dominio.publico as publico
from suricata.dominio.classificacao import (Atividade, atividade_de, classificar_tipo,
                                    data, nome_curto, resumo_estudo)
from suricata.rodada.coleta import atividade_de as atividade_de_coleta


def _assignment(**kwargs):
    base = dict(id="42", name="Lista 1", quiz_id=None, is_quiz_lti=False,
                submission_types=("online_text",), unlock_at=None, due_at=None,
                lock_at=None, points_possible=7.0, html_url="https://canvas.test/a",
                description="")
    base.update(kwargs)
    return SimpleNamespace(**base)


class ClassificacaoCompatibilityTests(unittest.TestCase):
    def test_publico_e_coleta_usam_a_mesma_entidade_e_fabrica(self):
        self.assertIs(publico.Atividade, Atividade)
        self.assertIs(atividade_de_coleta.__globals__["Atividade"], Atividade)
        self.assertIs(atividade_de_coleta.__globals__["atividade_de"], atividade_de)

    def test_atividade_e_congelada_e_chave_agenda_fecha_tem_contrato(self):
        unlock = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
        due = datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc)
        atividade = Atividade("101", "Curso", "42", "T", "tarefa", unlock, due, None, 7.0, "u")
        with self.assertRaises(Exception):
            atividade.tipo = "quiz"  # frozen
        self.assertEqual(atividade.chave, "101:42")
        self.assertIs(atividade.fecha, due)
        self.assertEqual(atividade.agenda, Atividade("101", "Curso", "42", "T", "tarefa",
                                                     unlock, due, None, 7.0, "u").agenda)
        self.assertNotEqual(atividade.agenda, Atividade("101", "Curso", "42", "T", "tarefa",
                                                        unlock, None, None, 7.0, "u").agenda)

    def test_classificar_tipo_matriz_completa(self):
        self.assertEqual(classificar_tipo(quiz_id=99, is_quiz_lti=False,
                                          submission_types=("online_quiz",), titulo="x"), "quiz")
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=True,
                                          submission_types=(), titulo="x"), "quiz")
        # D13: sem envio + nome de prova = avaliação (sem acento, p1..p4 também).
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False,
                                          submission_types=("none",), titulo="Prova 1"), "avaliacao")
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False,
                                          submission_types=("none",), titulo="P2"), "avaliacao")
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False,
                                          submission_types=("none",), titulo="AVALIACAO final"), "avaliacao")
        # F30: Khan etc. não é prova.
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False,
                                          submission_types=("none",), titulo="Khan Academy"), "tarefa")
        self.assertEqual(classificar_tipo(quiz_id=None, is_quiz_lti=False,
                                          submission_types=("online_text",), titulo="Prova"), "tarefa")

    def test_atividade_de_normaliza_titulo_datas_e_tipo(self):
        # A normalização remove tags HTML e chars de controle; entidades não são decodificadas.
        assignment = _assignment(name="  <b>Lista</b> 1 ", due_at="2026-09-17T03:00:00Z")
        atividade = atividade_de(assignment, "101", "Computabilidade - Ciência de Dados - 2026/2")
        self.assertEqual(atividade.titulo, "Lista 1")
        self.assertEqual(atividade.curso, "Computabilidade")
        self.assertEqual(atividade.due_at, datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc))
        self.assertEqual(atividade.tipo, "tarefa")
        self.assertEqual(atividade.fonte, "canvas")

    def test_data_contrato_completo(self):
        self.assertIsNone(data(None))
        self.assertIsNone(data(""))
        self.assertIsNone(data("não é data"))
        self.assertEqual(data("2026-09-15T12:00:00Z"),
                         datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc))
        # Naive vira UTC por padrão (comportamento original).
        self.assertEqual(data("2026-09-15T12:00:00").tzinfo, timezone.utc)

    def test_resumo_estudo_nunca_inventa(self):
        self.assertEqual(resumo_estudo(""), "")
        self.assertEqual(resumo_estudo("descrição sem padrão"), "")
        # Caso real citado no Canvas (sobrenome em maiúsculas): autor + capítulo + página.
        resumo = resumo_estudo("[1] GERSTING, Judith — base. Exercícios da lista: "
                               "Capítulo 4, páginas 205 a 227, exercícios 3, 4 e 5.")
        self.assertIn("Gersting", resumo)
        self.assertIn("cap. 4", resumo)
        self.assertIn("3 exercícios", resumo)

    def test_nome_curto(self):
        self.assertEqual(nome_curto("Computabilidade - Ciência de Dados - 2026/2"),
                         "Computabilidade")
        self.assertEqual(nome_curto("  Sem separador "), "Sem separador")


if __name__ == "__main__":
    unittest.main()
