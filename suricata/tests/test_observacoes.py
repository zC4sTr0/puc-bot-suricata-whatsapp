"""Observações de risco (D36): o PUC Bot constata fatos do calendário, nunca dá ordens."""
from __future__ import annotations

import re
import unittest
from datetime import datetime

from suricata.dominio.publico import (
    BRASILIA,
    Atividade,
    montar_vespera,
    observar,
    texto_aviso_prova,
    texto_lembrete,
    texto_mudou,
    texto_novo,
)


def brt(dia, h=0, m=0, mes=9):
    return datetime(2026, mes, dia, h, m, tzinfo=BRASILIA)


def item(titulo, tipo, fecha, abre=None, curso=("292189", "Introdução à Computação"), chave=None, pontos=25.0):
    return Atividade(curso[0], curso[1], chave or titulo, titulo, tipo, abre, None, fecha, pontos, "")


FUND = ("292185", "Fundamentos")
ALGO = ("289812", "Introdução a Algoritmos")


class ObservacoesTests(unittest.TestCase):
    def test_colisao_de_provas_no_mesmo_dia(self):
        p1 = item("Prova 1", "avaliacao", brt(23, 23, 59))
        p2 = item("Avaliação I", "avaliacao", brt(23, 8, 50), curso=FUND)
        self.assertEqual(observar(p1, [p1, p2], brt(21, 18)), ["no mesmo dia: Avaliação I (Fundamentos)"])
        p3 = item("Prova 1", "avaliacao", brt(23, 23, 59), curso=ALGO, chave="p3")
        self.assertEqual(observar(p1, [p1, p2, p3], brt(21, 18))[0], "no mesmo dia: mais 2 provas/quizzes")

    def test_sequencia_de_provas(self):
        p1 = item("Prova 1", "avaliacao", brt(23, 23, 59))
        vespera = item("Prova 1", "avaliacao", brt(22, 23, 59), curso=ALGO, chave="v")
        seguinte = item("Avaliação I", "avaliacao", brt(24, 23, 59), curso=FUND, chave="s")
        self.assertEqual(observar(p1, [p1, vespera], brt(20, 18)), ["na véspera tem Prova 1 (Introdução a Algoritmos)"])
        self.assertEqual(observar(p1, [p1, seguinte], brt(20, 18)), ["no dia seguinte tem Avaliação I (Fundamentos)"])
        self.assertEqual(observar(p1, [p1, vespera, seguinte], brt(20, 18)), ["provas em 3 dias seguidos"])

    def test_depois_de_fim_de_semana_ou_feriado_so_antes_da_pausa(self):
        segunda = item("Prova 2", "avaliacao", brt(21, 23, 59))
        self.assertEqual(observar(segunda, [segunda], brt(18, 18)), ["logo depois do fim de semana"])  # sexta
        self.assertEqual(observar(segunda, [segunda], brt(20, 18)), [])  # domingo: já não informa
        pos_feriadao = item("Prova 1", "avaliacao", brt(13, 23, 59, mes=10))
        self.assertEqual(observar(pos_feriadao, [pos_feriadao], brt(9, 18, mes=10)), ["logo depois do feriadão"])
        pos_feriado = item("Prova 3", "avaliacao", brt(3, 23, 59, mes=11))  # ter 03/11, depois de seg 02/11
        self.assertEqual(observar(pos_feriado, [pos_feriado], brt(30, 18, mes=10)), ["logo depois do feriadão"])
        # 07/09/2026 é segunda: terça 08/09 vem depois de sáb+dom+feriado = feriadão.
        pos_sete = item("Prova", "avaliacao", brt(8, 23, 59, mes=9))
        self.assertEqual(observar(pos_sete, [pos_sete], brt(4, 18, mes=9)), ["logo depois do feriadão"])
        # 21/04/2027 é quarta: quinta 22/04 vem depois de um feriado isolado.
        quinta = item("Prova", "avaliacao", datetime(2027, 4, 22, 23, 59, tzinfo=BRASILIA))
        self.assertEqual(observar(quinta, [quinta], datetime(2027, 4, 20, 18, tzinfo=BRASILIA)),
                         ["logo depois do feriado de 21/04"])

    def test_ultima_entrega_antes_da_prova_da_mesma_materia(self):
        comp = ("292184", "Computabilidade")
        lista5 = item("Lista 5", "tarefa", brt(21, 23, 59), curso=comp, pontos=1.5)
        prova = item("Prova 2", "avaliacao", brt(25, 23, 59), curso=comp)
        self.assertIn("última entrega antes da Prova 2 (sex 25/09)", observar(lista5, [lista5, prova], brt(19, 18)))
        lista6 = item("Lista 6", "tarefa", brt(24, 23, 59), curso=comp, pontos=1.5)
        self.assertEqual(observar(lista5, [lista5, lista6, prova], brt(19, 18)), [])  # não é a última
        outra_materia = item("Prova 2", "avaliacao", brt(25, 23, 59), curso=FUND, chave="f")
        self.assertEqual(observar(lista5, [lista5, outra_materia], brt(19, 18)), [])

    def test_entregas_no_mesmo_dia_e_fecha_de_manha(self):
        l1 = item("Lista 1", "tarefa", brt(16, 23, 59), pontos=7.0)
        l2 = item("Exercícios", "tarefa", brt(16, 23, 59), curso=ALGO, pontos=1.0)
        self.assertEqual(observar(l1, [l1, l2], brt(14, 18)), ["no mesmo dia vence Exercícios (Introdução a Algoritmos)"])
        cedo = item("Relatório", "tarefa", brt(17, 8, 50), abre=brt(10), pontos=5.0)
        self.assertEqual(observar(cedo, [cedo], brt(15, 18)), ["fecha às 08:50, de manhã"])

    def test_sem_fato_nao_inventa(self):
        solo = item("Prova 1", "avaliacao", brt(23, 23, 59))  # quarta, sem vizinhos
        self.assertEqual(observar(solo, [solo], brt(20, 18)), [])

    def test_no_maximo_duas_observacoes(self):
        p1 = item("Prova 2", "avaliacao", brt(21, 23, 59))
        outras = [item("P", "avaliacao", brt(21, 20), curso=FUND, chave="a"),
                  item("Q", "avaliacao", brt(22, 20), curso=ALGO, chave="b")]
        self.assertEqual(len(observar(p1, [p1, *outras], brt(18, 18))), 2)


class NuncaDaOrdensTests(unittest.TestCase):
    IMPERATIVOS = re.compile(r"(?i)\b(reserve|comece|começar|revise|revisar|estude|estudar|faça|fazer|"
                             r"não deixe|esteja|prepare|corra|lembre-se|bons estudos|ainda dá tempo|"
                             r"tudo indica|marcada em aula)\b")  # D37: inferência e fonte não viram texto

    def test_nenhum_texto_gerado_manda_fazer_algo(self):
        comp = ("292184", "Computabilidade")
        atividades = [
            item("Lista 5", "tarefa", brt(21, 23, 59), curso=comp, pontos=1.5),
            item("Prova 2", "avaliacao", brt(24, 23, 59), curso=comp),
            item("Quiz 3", "quiz", brt(22, 10, 25), abre=brt(22, 10, 10), pontos=3.0),
            item("Prova 1", "avaliacao", brt(22, 23, 59), abre=brt(22), curso=ALGO),
        ]
        textos = []
        for dia in range(17, 24):
            amanha = brt(dia + 1).date()
            textos.append(montar_vespera(atividades, amanha, brt(dia, 18))[0] or "")
            textos.append(texto_aviso_prova(atividades, amanha, brt(dia, 12)) or "")
        for a in atividades:
            textos += [texto_novo(a, brt(21, 9), atividades), texto_mudou(a)]
        textos.append(texto_lembrete(atividades[2]))
        for texto in textos:
            self.assertIsNone(self.IMPERATIVOS.search(texto), texto)
        self.assertTrue(any("↳" in t for t in textos))  # as observações realmente aparecem


if __name__ == "__main__":
    unittest.main()
