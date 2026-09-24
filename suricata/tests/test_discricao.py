"""Discrição do PUC Bot no grupo (decisões do titular em 2026-09-14).

O bot é público: só fala quando a informação é útil AGORA e o aluno não a teria a tempo
pelo ritmo normal (véspera 12h/18h e lembrete de quiz). Nunca de madrugada.
Estes testes fixam a filosofia; mude-os só com nova decisão do titular.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from suricata.dominio.publico import (
    BRASILIA,
    Atividade,
    anuncio_de_agora,
    decidir,
    montar_vespera,
    precisa_lembrete,
)
from suricata.rodada import OUTBOX, executar, planejar_aviso_prova, planejar_vespera
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import JID, CanvasFalso, PonteFalsa, iso


def brt(dia, h=0, m=0, mes=9):
    return datetime(2026, mes, dia, h, m, tzinfo=BRASILIA)


def atividade(titulo, tipo, abre=None, fecha=None, chave="1"):
    # Matéria comum (a pesada tem regras próprias em MateriaPesadaTests).
    return Atividade("292185", "Fundamentos", chave, titulo, tipo, abre, None, fecha, 25.0, "")


class PublicacaoSoSeForSurpresaTests(unittest.TestCase):
    def test_prova_de_novembro_publicada_em_setembro_nao_avisa(self):
        prova = atividade("Prova 3", "avaliacao", None, brt(13, 23, 59, mes=11))
        self.assertEqual(decidir(prova, brt(11, 21)), "sem_urgencia")  # sexta à noite, em setembro

    def test_hoje_avisa_amanha_so_depois_da_vespera_ou_sem_aula_amanha(self):
        quiz_hoje = atividade("Quiz", "quiz", brt(15, 10, 10), brt(15, 10, 25))
        self.assertEqual(decidir(quiz_hoje, brt(15, 8, 44)), "alertar")
        prova_amanha = atividade("Prova", "avaliacao", brt(16), brt(16, 23, 59))
        self.assertEqual(decidir(prova_amanha, brt(15, 11)), "alertar")  # novidade imediata de amanhã
        self.assertEqual(decidir(prova_amanha, brt(15, 19)), "alertar")       # véspera já passou
        entrega_sabado = atividade("Lista", "tarefa", None, brt(19, 23, 59))
        self.assertEqual(decidir(entrega_sabado, brt(18, 10)), "alertar")     # sábado não tem véspera

    def test_quiz_sem_data_nenhuma_e_surpresa(self):
        self.assertEqual(decidir(atividade("Quiz surpresa", "quiz"), brt(15, 9)), "alertar")
        self.assertEqual(decidir(atividade("Trabalho", "tarefa"), brt(15, 9)), "sem_urgencia")

    def test_recado_so_se_fala_de_hoje_ou_amanha(self):
        agora = brt(15, 9)
        self.assertTrue(anuncio_de_agora("Aviso", "A prova de amanhã foi adiada", agora))
        self.assertTrue(anuncio_de_agora("Prova", "Será dia 16/09 no laboratório", agora))
        self.assertFalse(anuncio_de_agora("Prova 3", "Conteúdo da prova de novembro: capítulos 4 e 5", agora))
        self.assertFalse(anuncio_de_agora("Prova", "Dia 16/10", agora))


class VesperaDiscretaTests(unittest.TestCase):
    def test_sem_nada_amanha_silencio_mesmo_com_prova_chegando(self):
        prova_semana_que_vem = atividade("Prova 2", "avaliacao", None, brt(18, 23, 59))
        self.assertEqual(montar_vespera([prova_semana_que_vem], brt(16).date(), brt(15, 18)), (None, [], []))

    def test_chegando_cita_cada_prova_uma_vez(self):
        entrega = atividade("Lista", "tarefa", None, brt(16, 23, 59), chave="lista")
        prova = atividade("Prova 2", "avaliacao", None, brt(18, 23, 59), chave="p2")
        memoria: dict = {}
        primeira = planejar_vespera([entrega, prova], memoria, brt(15, 18))
        self.assertIn("Prova 2", primeira.texto)
        entrega2 = atividade("Lista 2", "tarefa", None, brt(17, 23, 59), chave="lista2")
        segunda = planejar_vespera([entrega2, prova], memoria, brt(16, 18))
        self.assertNotIn("• sex 18/09", segunda.texto)  # item de "Próximos dias" não se repete

    def test_18h_nao_repete_prova_do_meio_dia_mas_inclui_a_publicada_depois(self):
        prova = atividade("Prova 1", "avaliacao", brt(16), brt(16, 23, 59), chave="p1")
        memoria: dict = {}
        self.assertIsNotNone(planejar_aviso_prova([prova], memoria, brt(15, 12)))
        self.assertIsNone(planejar_vespera([prova], memoria, brt(15, 18)))  # só tinha a prova: silêncio
        nova = atividade("Quiz", "quiz", brt(16, 10, 10), brt(16, 10, 25), chave="q")
        memoria2 = {"avisos_prova": {"2026-09-16": ["292185:p1"]}}
        texto = planejar_vespera([prova, nova], memoria2, brt(15, 18)).texto
        self.assertIn("Quiz", texto)
        self.assertNotIn("Prova 1", texto)

    def test_memoria_antiga_do_meio_dia_nao_quebra(self):
        prova = atividade("Prova 1", "avaliacao", brt(16), brt(16, 23, 59))
        evento = planejar_vespera([prova], {"avisos_prova": {"2026-09-16": "enviado"}}, brt(15, 18))
        self.assertIn("Prova 1", evento.texto)

    def test_vespera_nao_e_planejada_as_23h(self):
        entrega = atividade("Lista", "tarefa", None, brt(16, 23, 59))
        self.assertIsNone(planejar_vespera([entrega], {}, brt(15, 23, 5)))


class LembreteSoParaQuizRelampagoTests(unittest.TestCase):
    def test_quiz_aberto_por_dias_nao_tem_lembrete(self):
        curto = atividade("Quiz", "quiz", brt(16, 10, 10), brt(16, 10, 25))
        longo = atividade("Quiz semanal", "quiz", brt(16, 10, 10), brt(23, 23, 59))
        self.assertTrue(precisa_lembrete(curto, brt(16, 10)))
        self.assertFalse(precisa_lembrete(longo, brt(16, 10)))


class MadrugadaELoteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.objetos = ObjetosLocais(Path(self._tmp.name))
        self.canvas = CanvasFalso()

    def tearDown(self):
        self._tmp.cleanup()

    def rodar(self, agora, ponte):
        return executar(objetos=self.objetos, canvas=self.canvas.cliente(), entrega_ligada=True,
                        grupo_jid=JID, ponte=ponte, agora=lambda: agora)

    def test_surpresas_da_madrugada_esperam_ate_7h_e_saem_numa_mensagem(self):
        ponte = PonteFalsa()
        self.rodar(brt(15, 1), ponte)  # linha de base
        itens = []
        for i in range(3):
            abre = brt(15, 10, 10 + i)
            itens.append({"id": 100 + i, "name": f"Quiz {i}", "points_possible": 3, "quiz_id": 900 + i,
                          "unlock_at": iso(abre.astimezone(timezone.utc)),
                          "lock_at": iso((abre + timedelta(minutes=15)).astimezone(timezone.utc)), "due_at": None,
                          "html_url": f"https://pucminas.instructure.com/courses/292184/assignments/{100 + i}"})
        self.canvas.assignments["292184"] = itens
        _, rel = self.rodar(brt(15, 3), ponte)
        self.assertEqual((len(rel["eventos"]), ponte.lotes), (3, []))  # decidido, mas nada sai às 3h
        self.assertTrue(rel["entrega"]["silencio"])
        self.rodar(brt(15, 7, 30), ponte)
        self.assertEqual(len(ponte.lotes), 1)
        (mensagem,) = ponte.lotes[0]
        self.assertTrue(mensagem["texto"].startswith("🚨 🎓 *PUC Bot*: 3 surpresas no Canvas"))
        registros = json.loads(self.objetos.ler(OUTBOX).dados)
        self.assertEqual({r["estado"] for r in registros}, {"sent"})

    def test_publicacao_segurada_na_madrugada_nao_gera_lembrete_repetido_as_7h(self):
        ponte = PonteFalsa()
        self.rodar(brt(15, 1), ponte)
        abre = brt(15, 7, 40)
        self.canvas.assignments["292184"] = [{"id": 5, "name": "Quiz cedo", "points_possible": 3, "quiz_id": 5,
                                              "unlock_at": iso(abre.astimezone(timezone.utc)),
                                              "lock_at": iso((abre + timedelta(minutes=15)).astimezone(timezone.utc)),
                                              "due_at": None, "html_url": ""}]
        self.rodar(brt(15, 3), ponte)
        _, rel = self.rodar(brt(15, 7, 30), ponte)
        self.assertEqual([e["tipo"] for e in rel["eventos"]], [])
        self.assertEqual([[m["event_id"].split(":")[1] for m in lote] for lote in ponte.lotes], [["novo"]])


if __name__ == "__main__":
    unittest.main()


class TextoDaMadrugadaTests(unittest.TestCase):
    def test_prova_de_amanha_publicada_23h30_sai_as_7h_dizendo_hoje(self):
        from suricata.dominio.publico import texto_novo

        prova = atividade("Prova 1", "avaliacao", brt(16), brt(16, 23, 59))
        self.assertEqual(decidir(prova, brt(15, 23, 30)), "alertar")
        self.assertTrue(texto_novo(prova, brt(15, 23, 30)).startswith("🚨 🎓 *PUC Bot*: prova hoje no Canvas!"))
        self.assertTrue(texto_novo(prova, brt(15, 19)).startswith("🚨 🎓 *PUC Bot*: prova amanhã no Canvas!"))
