"""Regressão: o corte noturno não deve expirar eventos criados às 07:00."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from suricata.message_id import message_id
from suricata.rodada import OUTBOX, Evento, OutboxSincronizado, entregar
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import JID, PonteFalsa


class Corte21hEventoAtualTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.objetos = ObjetosLocais(self.root)
        self.fila = OutboxSincronizado(self.objetos, self.root)
        self.ponte = PonteFalsa()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def brt(dia: int, hora: int, minuto: int = 0) -> datetime:
        from suricata.publico import BRASILIA

        return datetime(2026, 9, dia, hora, minuto, tzinfo=BRASILIA)

    def _estado(self) -> dict[str, dict]:
        objeto = self.objetos.ler(OUTBOX)
        return {registro["event_id"]: registro for registro in json.loads(objeto.dados or b"[]")}

    def test_evento_da_rodada_das_07h_e_entregue_mas_pendente_overnight_e_cortada(self):
        noite = self.brt(15, 21)
        pendente = "grupo:overnight:comum"
        self.fila.outbox.adicionar(
            {
                "event_id": pendente,
                "message_id": message_id(JID, pendente),
                "texto": "pendência antiga",
                "expira_em": self.brt(16, 12).astimezone(timezone.utc).isoformat(),
            },
            agora=noite,
        )
        self.fila.publicar()

        atual = Evento("mudou", "grupo:mudou:rodada-07h", "mudança descoberta agora")
        resumo = entregar(self.fila, self.ponte, JID, [atual], self.brt(16, 7))

        self.assertEqual(resumo["pendentes_enviados"], 1)
        self.assertEqual(self.ponte.lotes[0][0]["event_id"], atual.event_id)
        estados = self._estado()
        self.assertEqual(estados[pendente]["estado"], "expirado")
        self.assertEqual(estados[atual.event_id]["estado"], "sent")

    def test_contrato_do_corte_recebe_eventos_da_rodada_sem_flag_persistida(self):
        atual = "grupo:atual:sem-flag"
        comum = "grupo:overnight:sem-flag"
        self.fila.outbox.adicionar(
            {
                "event_id": atual,
                "message_id": message_id(JID, atual),
                "texto": "atual",
                "expira_em": self.brt(16, 12).astimezone(timezone.utc).isoformat(),
            },
            agora=self.brt(16, 7),
        )
        self.fila.outbox.adicionar(
            {
                "event_id": comum,
                "message_id": message_id(JID, comum),
                "texto": "overnight",
                "expira_em": self.brt(16, 12).astimezone(timezone.utc).isoformat(),
            },
            agora=self.brt(15, 21),
        )
        self.fila.publicar()

        corte = self.fila.outbox.cortar_apos_21h(
            agora=self.brt(16, 7), eventos_atuais={atual}
        )
        self.fila.publicar()

        self.assertEqual(corte, {"devolvidos": 0, "expirados": 1, "preservados": 1})
        estados = self._estado()
        self.assertEqual(estados[atual]["estado"], "pending")
        self.assertEqual(estados[comum]["estado"], "expirado")


if __name__ == "__main__":
    unittest.main()
