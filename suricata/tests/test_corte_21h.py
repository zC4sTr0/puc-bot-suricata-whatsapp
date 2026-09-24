"""Regressões do corte absoluto de envio às 21:00 (horário de Brasília)."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from suricata.rodada import OUTBOX, Evento, OutboxSincronizado, entregar, executar
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import JID, CanvasFalso, PonteFalsa


class Corte21hTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.objetos = ObjetosLocais(Path(self._tmp.name))
        self.canvas = CanvasFalso()
        self.ponte = PonteFalsa()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @staticmethod
    def brt(dia: int, hora: int, minuto: int = 0) -> datetime:
        from suricata.dominio.publico import BRASILIA

        return datetime(2026, 9, dia, hora, minuto, tzinfo=BRASILIA)

    @staticmethod
    def quiz(identificador: int, inicio: datetime, fim: datetime, nome: str = "Quiz") -> dict:
        return {
            "id": identificador,
            "name": nome,
            "points_possible": 3,
            "quiz_id": 900 + identificador,
            "unlock_at": inicio.isoformat(),
            "lock_at": fim.isoformat(),
            "due_at": None,
            "html_url": "https://pucminas.instructure.com/atividade",
        }

    def rodar(self, agora: datetime) -> tuple[int, dict]:
        return executar(
            objetos=self.objetos,
            canvas=self.canvas.cliente(),
            entrega_ligada=True,
            grupo_jid=JID,
            ponte=self.ponte,
            agora=lambda: agora,
        )

    def estados_outbox(self) -> list[dict]:
        dados = self.objetos.ler(OUTBOX).dados
        return json.loads(dados) if dados else []

    def test_nova_atividade_do_mesmo_dia_apos_21h_e_descartada(self):
        self.rodar(self.brt(15, 12))
        inicio, fim = self.brt(15, 20), self.brt(15, 23)
        self.canvas.assignments["292184"] = [self.quiz(1, inicio, fim)]

        codigo, relatorio = self.rodar(self.brt(15, 21, 1))

        self.assertEqual(codigo, 0)
        self.assertEqual(relatorio["entrega"]["pendentes_enviados"], 0)
        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados_outbox(), [])

    def test_descoberta_literal_as_2100_de_ontem_vai_para_07_de_hoje(self):
        self.rodar(self.brt(15, 12))
        inicio, fim = self.brt(16, 10), self.brt(16, 10, 15)
        self.canvas.assignments["292184"] = [self.quiz(2, inicio, fim)]

        # Caso literal: descoberta exatamente às 21:00 de ontem.
        self.rodar(self.brt(15, 21))

        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual([registro["estado"] for registro in self.estados_outbox()], ["pending"])

        self.rodar(self.brt(16, 7, 30))
        self.assertEqual(len(self.ponte.lotes), 1)
        self.assertEqual(self.estados_outbox()[0]["estado"], "sent")

    def test_novidade_amanha_apos_21h_preserva_evento_para_0730(self):
        self.rodar(self.brt(15, 12))
        inicio, fim = self.brt(16, 10), self.brt(16, 10, 15)
        self.canvas.assignments["292184"] = [self.quiz(3, inicio, fim)]

        self.rodar(self.brt(15, 21, 1))

        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual([registro["estado"] for registro in self.estados_outbox()], ["pending"])

        self.rodar(self.brt(16, 7, 30))
        self.assertEqual(len(self.ponte.lotes), 1)
        self.assertEqual(self.estados_outbox()[0]["estado"], "sent")

    def test_nova_atividade_do_mesmo_dia_ja_presente_ontem_nao_e_excecao(self):
        inicio, fim = self.brt(15, 20), self.brt(15, 20, 15)
        self.canvas.assignments["292184"] = [self.quiz(4, inicio, fim)]
        self.rodar(self.brt(14, 10))

        self.rodar(self.brt(15, 21, 1))

        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados_outbox(), [])

    def test_mudanca_e_lembrete_explicitos_nao_enviam_apos_21h(self):
        fila = OutboxSincronizado(self.objetos, Path(self._tmp.name))
        eventos = [Evento("mudou", "grupo:mudou:x", "mudou"), Evento("lembrete", "grupo:lembrete:x", "lembrete")]

        resumo = entregar(fila, self.ponte, JID, eventos, self.brt(15, 21))

        self.assertEqual(resumo["pendentes_enviados"], 0)
        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados_outbox(), [])

    def test_autorizacao_corte_sobrevive_a_rodada_seguinte_antes_da_meia_noite(self):
        # Regressão 24/09: quiz descoberto às 23:40 expirava na rodada das 23:50.
        self.rodar(self.brt(15, 20))
        inicio, fim = self.brt(16, 10, 10), self.brt(16, 10, 25)
        self.canvas.assignments["292184"] = [self.quiz(4, inicio, fim)]

        for minuto in (40, 50):
            self.rodar(self.brt(15, 23, minuto))
            self.assertEqual([registro["estado"] for registro in self.estados_outbox()], ["pending"])
        self.assertEqual(self.ponte.lotes, [])

        self.rodar(self.brt(16, 7, 30))
        self.assertEqual(len(self.ponte.lotes), 1)
        self.assertEqual(self.estados_outbox()[0]["estado"], "sent")


if __name__ == "__main__":
    unittest.main()
