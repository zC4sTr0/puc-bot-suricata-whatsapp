"""Regressões das quatro janelas de anúncio de novidade do Canvas."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from suricata.rodada import OUTBOX, executar
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import CanvasFalso, PonteFalsa

JID = "120363000000000000-1700000000@g.us"


class JanelasNovidadeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.objetos = ObjetosLocais(Path(self.tmp.name))
        self.canvas = CanvasFalso()
        self.canvas.cursos.append({"id": 292185, "name": "Fundamentos de Ciência de Dados e Inteligência Artificial"})
        self.canvas.assignments["292185"] = []

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def brt(dia: int, hora: int, minuto: int = 0) -> datetime:
        from suricata.dominio.publico import BRASILIA

        return datetime(2026, 9, dia, hora, minuto, tzinfo=BRASILIA)

    def quiz(self, identificador: int, unlock: datetime, lock: datetime) -> dict:
        return {
            "id": identificador,
            "name": "Quiz de novidade",
            "points_possible": 3,
            "quiz_id": 900 + identificador,
            "unlock_at": unlock.isoformat(),
            "lock_at": lock.isoformat(),
            "due_at": None,
            "html_url": f"https://pucminas.instructure.com/courses/292185/assignments/{identificador}",
        }

    def rodar(self, agora: datetime, ponte: PonteFalsa | None = None) -> tuple[int, dict]:
        return executar(
            objetos=self.objetos,
            canvas=self.canvas.cliente(),
            entrega_ligada=ponte is not None,
            grupo_jid=JID if ponte is not None else None,
            ponte=ponte,
            agora=lambda: agora,
        )

    def outbox(self) -> list[dict]:
        dados = self.objetos.ler(OUTBOX).dados
        return json.loads(dados) if dados else []

    def novidade(self) -> dict | None:
        return next((registro for registro in self.outbox() if ":novo:292185:1435384" in registro["event_id"]), None)

    def lotes_da_novidade(self, ponte: PonteFalsa) -> list[list[dict]]:
        return [lote for lote in ponte.lotes if any(":novo:292185:1435384" in item["event_id"] for item in lote)]

    def preparar_linha_de_base(self, agora: datetime) -> None:
        self.rodar(agora)

    def test_novidade_amanha_descoberta_as_10_sai_imediatamente_sem_resumo_duplicado(self):
        self.preparar_linha_de_base(self.brt(16, 9))
        self.canvas.assignments["292185"] = [self.quiz(1435384, self.brt(17, 10, 10), self.brt(17, 10, 25))]
        ponte = PonteFalsa()

        # 07:00–11:59 é novidade útil agora, e não espera o resumo das 18:00.
        self.rodar(self.brt(16, 10), ponte)
        self.assertEqual(len(self.lotes_da_novidade(ponte)), 1)
        self.assertEqual(self.novidade()["estado"], "sent")

        # O evento novo ocupa o lugar do resumo/véspera; não há duplicata.
        self.rodar(self.brt(16, 18), ponte)
        self.assertEqual([item["event_id"] for lote in ponte.lotes for item in lote],
                         ["grupo:novo:292185:1435384"])
        self.rodar(self.brt(17, 7), ponte)
        self.assertEqual(len(self.lotes_da_novidade(ponte)), 1)

    def test_novidade_amanha_descoberta_as_1810_sai_somente_as_07(self):
        self.preparar_linha_de_base(self.brt(16, 9))
        self.canvas.assignments["292185"] = [self.quiz(1435384, self.brt(17, 10, 10), self.brt(17, 10, 25))]
        ponte = PonteFalsa()

        self.rodar(self.brt(16, 18, 10), ponte)

        self.assertEqual(self.lotes_da_novidade(ponte), [])
        self.assertEqual(self.novidade()["estado"], "pending")

        self.rodar(self.brt(17, 7), ponte)
        self.assertEqual(len(self.lotes_da_novidade(ponte)), 1)
        self.assertEqual(self.novidade()["estado"], "sent")

    def test_novidade_amanha_descoberta_as_2000_sai_somente_as_07(self):
        self.preparar_linha_de_base(self.brt(16, 9))
        self.canvas.assignments["292185"] = [self.quiz(1435384, self.brt(17, 10, 10), self.brt(17, 10, 25))]
        ponte = PonteFalsa()

        self.rodar(self.brt(16, 20), ponte)

        self.assertEqual(self.lotes_da_novidade(ponte), [])
        self.assertEqual(self.novidade()["estado"], "pending")

        self.rodar(self.brt(17, 7), ponte)
        self.assertEqual(len(self.lotes_da_novidade(ponte)), 1)
        self.assertEqual(self.novidade()["estado"], "sent")

    def test_evento_do_mesmo_dia_entre_18_e_2059_e_imediato(self):
        from suricata.dominio.planejamento import janela_novidade
        from suricata.dominio.publico import Atividade

        abre = self.brt(16, 18, 10)
        atividade = Atividade("292185", "Fundamentos", "Quiz", "1435384", "quiz", abre,
                              None, self.brt(16, 18, 25), 3.0, "", "canvas")
        self.assertEqual(janela_novidade(atividade, self.brt(16, 18, 10)), "imediata")
        self.assertEqual(janela_novidade(atividade, self.brt(16, 20, 59)), "imediata")

    def test_evento_do_mesmo_dia_entre_12_e_18_nao_fica_retido(self):
        self.preparar_linha_de_base(self.brt(16, 9))
        self.canvas.assignments["292185"] = [self.quiz(1435384, self.brt(16, 13, 10), self.brt(16, 13, 25))]
        ponte = PonteFalsa()

        self.rodar(self.brt(16, 13), ponte)

        self.assertEqual(len(self.lotes_da_novidade(ponte)), 1)
        self.assertEqual(self.novidade()["estado"], "sent")

    def test_publicacao_as_21h_descoberta_na_rodada_quiz_amanha_pending_e_um_envio_as_07(self):
        """Aceite literal: publicação 21:00 BRT, descoberta nessa rodada, sem reenvio."""
        self.preparar_linha_de_base(self.brt(16, 20, 50))
        self.canvas.assignments["292185"] = [self.quiz(1435384, self.brt(17, 10, 10), self.brt(17, 10, 25))]
        ponte = PonteFalsa()

        # Descoberta às 21:00: não publica à noite, mas deixa a novidade durável.
        self.rodar(self.brt(16, 21), ponte)

        self.assertEqual(self.lotes_da_novidade(ponte), [])
        self.assertIsNotNone(self.novidade())
        self.assertEqual(self.novidade()["estado"], "pending")

        self.rodar(self.brt(17, 7), ponte)
        self.rodar(self.brt(17, 7, 10), ponte)

        self.assertEqual(len(self.lotes_da_novidade(ponte)), 1)
        self.assertEqual(self.novidade()["estado"], "sent")

    def test_item_descoberto_em_sombra_nao_e_consumido_antes_do_outbox(self):
        self.canvas.assignments["292185"] = [self.quiz(1435384, self.brt(17, 10, 10), self.brt(17, 10, 25))]
        self.preparar_linha_de_base(self.brt(16, 11, 50))
        ponte = PonteFalsa()

        self.rodar(self.brt(16, 18), ponte)

        self.assertEqual(self.lotes_da_novidade(ponte), [])
        self.assertIsNotNone(self.novidade())

    def test_novidade_sem_ack_permanece_pendente(self):
        self.preparar_linha_de_base(self.brt(16, 9))
        self.canvas.assignments["292185"] = [self.quiz(1435384, self.brt(16, 10, 10), self.brt(16, 10, 25))]
        ponte = PonteFalsa(ack=False)

        self.rodar(self.brt(16, 10), ponte)

        self.assertEqual(len(self.lotes_da_novidade(ponte)), 1)
        self.assertEqual(self.novidade()["estado"], "pending")


if __name__ == "__main__":
    unittest.main()
