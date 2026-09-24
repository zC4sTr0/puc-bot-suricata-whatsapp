"""Ataques RED contra o corte absoluto de entrega às 21:00 BRT.

Os cenários usam somente armazenamento local e dublês já existentes no repo.
Eles registram invariantes do corte, não efeitos externos reais.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from suricata.dominio.message_id import message_id
from suricata.rodada import OUTBOX, OutboxSincronizado, entregar
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import JID, PonteFalsa


class Corte21hAdversarialTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.objetos = ObjetosLocais(self.root)
        self.fila = OutboxSincronizado(self.objetos, self.root)
        self.ponte = PonteFalsa()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @staticmethod
    def brt(dia: int, hora: int, minuto: int = 0, segundo: int = 0) -> datetime:
        from suricata.dominio.publico import BRASILIA

        return datetime(2026, 9, dia, hora, minuto, segundo, tzinfo=BRASILIA)

    def registro(self, event_id: str, criado_em: datetime, *, preservar: bool = False) -> dict:
        registro = {
            "event_id": event_id,
            "message_id": message_id(JID, event_id),
            "texto": f"texto-{event_id}",
            "expira_em": "2026-09-16T12:00:00+00:00",
        }
        if preservar:
            registro["preservar_apos_21h"] = True
        return registro

    def estados(self) -> list[dict]:
        obj = self.objetos.ler(OUTBOX)
        return json.loads(obj.dados) if obj.dados else []

    def entregar_em(self, momento: datetime) -> dict:
        return entregar(self.fila, self.ponte, JID, [], momento)

    def test_relogio_que_atravessa_21h_bloqueia_antes_da_ponte(self):
        """Uma rodada iniciada no limite não pode enviar após o relógio cruzá-lo."""
        evento = self.registro("grupo:novo:atravessou-21h", self.brt(15, 20, 59, 59))
        self.fila.outbox.adicionar(evento, agora=self.brt(15, 20, 59, 59))

        resumo = self.entregar_em(self.brt(15, 21, 0, 1))

        self.assertEqual(resumo["pendentes_enviados"], 0)
        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados()[0]["estado"], "expirado")

    def test_revalidacao_entre_claim_e_ponte_bloqueia_envio(self):
        evento = self.registro("grupo:novo:revalidacao", self.brt(15, 20, 59, 59))
        self.fila.outbox.adicionar(evento, agora=self.brt(15, 20, 59, 59))
        leituras = iter((self.brt(15, 20, 59, 59), self.brt(15, 20, 59, 59), self.brt(15, 21, 0, 1)))

        resumo = entregar(self.fila, self.ponte, JID, [], lambda: next(leituras))

        self.assertEqual(resumo["pendentes_enviados"], 0)
        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados()[0]["estado"], "expirado")

    def test_pending_comum_criado_antes_do_corte_nao_e_enviado_as_0730(self):
        """Pendência antiga não pode ser carregada artificialmente para a manhã."""
        criado = self.brt(15, 20, 59, 59)
        self.fila.outbox.adicionar(self.registro("grupo:comum:antes-do-corte", criado), agora=criado)

        self.entregar_em(self.brt(15, 21, 0, 1))
        resumo = self.entregar_em(self.brt(16, 7, 30))

        self.assertEqual(resumo["pendentes_enviados"], 0)
        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados()[0]["estado"], "expirado")

    def test_pending_com_preservar_apos_21h_forjado_nao_bypassa_o_corte(self):
        """Um marcador persistido manualmente não cria a exceção matinal."""
        criado = self.brt(15, 20, 59, 59)
        self.fila.outbox.adicionar(
            self.registro("grupo:forjado:preservacao", criado, preservar=True), agora=criado
        )

        self.entregar_em(self.brt(15, 21, 1))
        resumo = self.entregar_em(self.brt(16, 7, 30))

        self.assertEqual(resumo["pendentes_enviados"], 0)
        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados()[0]["estado"], "expirado")

    def test_in_flight_recuperado_as_0730_nao_reabre_pendencia_antiga(self):
        """Crash antes do corte não pode transformar uma pendência antiga em envio matinal."""
        criado = self.brt(15, 20, 59, 59)
        event_id = "grupo:crash:antes-do-corte"
        self.fila.outbox.adicionar(self.registro(event_id, criado), agora=criado)
        self.fila.outbox.reivindicar(event_id, agora=criado)
        self.fila.publicar()

        resumo = self.entregar_em(self.brt(16, 7, 30))

        self.assertEqual(resumo["pendentes_enviados"], 0)
        self.assertEqual(self.ponte.lotes, [])
        self.assertEqual(self.estados()[0]["estado"], "expirado")


if __name__ == "__main__":
    unittest.main()
