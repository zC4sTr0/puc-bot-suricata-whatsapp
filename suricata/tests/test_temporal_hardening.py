"""Cobertura adversarial das fronteiras BRT e suas composições.

Este arquivo usa somente as fachadas públicas da rodada e doubles já existentes.
As expectativas são literais: segundos não devem alterar uma janela que é
expressamente definida por hora/minuto, e uma mesma novidade não pode reaparecer
como texto duplicado ao atravessar o corte noturno.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from suricata.dominio.corte_rodada import corte_21h, janela_manha
from suricata.dominio.planejamento import janela_novidade
from suricata.dominio.publico import Atividade
from suricata.rodada import OUTBOX, Destino, executar, executar_destinos
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import JID, CanvasFalso, PonteFalsa, quiz


class TemporalHardeningTests(unittest.TestCase):
    @staticmethod
    def brt(hora: int, minuto: int = 0, segundo: int = 0) -> datetime:
        from suricata.dominio.publico import BRASILIA

        return datetime(2026, 9, 16, hora, minuto, segundo, tzinfo=BRASILIA)

    @staticmethod
    def atividade(dia: int, *, chave: str = "amanha") -> Atividade:
        from suricata.dominio.publico import BRASILIA

        abre = datetime(2026, 9, dia, 10, 0, tzinfo=BRASILIA)
        fecha = abre + timedelta(minutes=15)
        return Atividade("292184", "Computabilidade", chave, "Quiz", "quiz", abre,
                         None, fecha, 3.0, "https://example.test/quiz")

    def test_fronteiras_de_corte_e_excecao_matinal_preservam_segundos(self):
        casos = [
            (self.brt(7), False, True),
            (self.brt(7, segundo=1), False, True),
            (self.brt(7, 1), False, False),
            (self.brt(20, 59, 59), False, False),
            (self.brt(21), True, False),
            (self.brt(21, segundo=1), True, False),
        ]
        for agora, cortada, matinal in casos:
            with self.subTest(agora=agora.isoformat()):
                self.assertEqual(corte_21h(agora), cortada)
                self.assertEqual(janela_manha(agora), matinal)

    def test_janela_de_novidade_separa_115959_120000_175959_e_180000(self):
        atividade = self.atividade(17)
        casos = [
            (self.brt(11, 59, 59), "imediata"),
            (self.brt(12), "18h"),
            (self.brt(17, 59, 59), "18h"),
            (self.brt(18), "07h"),
        ]
        for agora, esperada in casos:
            with self.subTest(agora=agora.isoformat()):
                self.assertEqual(janela_novidade(atividade, agora), esperada)

    def test_novidade_do_mesmo_dia_e_imediata_ate_205959_e_silenciosa_no_corte(self):
        atividade = self.atividade(16)
        self.assertEqual(janela_novidade(atividade, self.brt(20, 59, 59)), "imediata")
        self.assertEqual(janela_novidade(atividade, self.brt(21)), "silencio")
        self.assertEqual(janela_novidade(atividade, self.brt(21, 0, 1)), "silencio")

    def test_anuncios_indisponiveis_nao_bloqueiam_quiz_nem_criam_anuncio_fantasma(self):
        canvas = CanvasFalso()
        canvas.status_anuncios = 500
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            executar(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=False,
                     grupo_jid=JID, ponte=None, agora=lambda: self.brt(9))
            canvas.assignments["292184"] = [
                quiz(7, abre=self.brt(15), fecha=self.brt(15, 15))
            ]
            codigo, relatorio = executar(
                objetos=objetos, canvas=canvas.cliente(), entrega_ligada=False,
                grupo_jid=JID, ponte=None, agora=lambda: self.brt(10))
            self.assertEqual((codigo, relatorio["estado"]), (0, "parcial"))
            self.assertEqual([evento["tipo"] for evento in relatorio["eventos"]], ["novo"])

    def test_dois_destinos_recebem_a_mesma_novidade_sem_compartilhar_estado(self):
        canvas = CanvasFalso()
        destinos = [Destino("grupo", JID, "grupo"),
                    Destino("trabalho", "120363000000000001@g.us", "destinos/trabalho")]
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            base = self.brt(6, 50)
            executar_destinos(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=False,
                              ponte=None, destinos=destinos, agora=lambda: base)
            canvas.assignments["292184"] = [
                quiz(8, abre=self.brt(17, 10), fecha=self.brt(17, 10, 15))
            ]
            ponte = PonteFalsa()
            codigo, relatorios = executar_destinos(
                objetos=objetos, canvas=canvas.cliente(), entrega_ligada=True,
                ponte=ponte, destinos=destinos, agora=lambda: self.brt(7))
            self.assertEqual((codigo, len(relatorios), len(ponte.lotes)), (0, 2, 2))
            self.assertEqual({lote[0]["event_id"] for lote in ponte.lotes}, {"grupo:novo:292184:8"})
            self.assertEqual([r["destino"] for r in relatorios], ["grupo", "trabalho"])
            for prefixo in ("grupo", "destinos/trabalho"):
                registros = json.loads(objetos.ler(f"{prefixo}/outbox.json").dados)
                self.assertEqual([r["event_id"] for r in registros], ["grupo:novo:292184:8"])

    def test_pendente_overnight_nao_duplica_texto_ao_atravessar_2100_e_070001(self):
        canvas = CanvasFalso()
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            base = self.brt(20, 59, 59)
            executar(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=False,
                     grupo_jid=JID, ponte=None, agora=lambda: base)
            canvas.assignments["292184"] = [
                quiz(9, abre=self.brt(17, 10), fecha=self.brt(17, 10, 15))
            ]
            ponte = PonteFalsa()
            executar(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=True,
                     grupo_jid=JID, ponte=ponte, agora=lambda: self.brt(21))
            self.assertEqual(ponte.lotes, [])
            executar(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=True,
                     grupo_jid=JID, ponte=ponte, agora=lambda: self.brt(7, segundo=1))
            executar(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=True,
                     grupo_jid=JID, ponte=ponte, agora=lambda: self.brt(7, minuto=1))
            eventos = [item for lote in ponte.lotes for item in lote]
            self.assertEqual([item["event_id"] for item in eventos], ["grupo:novo:292184:9"])
            self.assertEqual(len({item["texto"] for item in eventos}), 1)
            registros = json.loads(objetos.ler(OUTBOX).dados)
            self.assertEqual([r["estado"] for r in registros], ["sent"])


if __name__ == "__main__":
    unittest.main()
