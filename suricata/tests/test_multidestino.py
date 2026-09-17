"""Testes offline do planejamento multi-destino."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from suricata.rodada import Destino, destinos_do_ambiente, executar_destinos
from suricata.storage.gcs import ObjetosLocais
from suricata.tests.test_rodada import CanvasFalso, PonteFalsa, quiz


class MultiDestinoTests(unittest.TestCase):
    def test_configuracao_e_janela_brt_sao_opt_in(self):
        jid = "120363000000000000-1700000000@g.us"
        destinos = destinos_do_ambiente({
            "SURICATA_GRUPO_JID": "120363000000000000@g.us",
            "SURICATA_DESTINOS_JSON": json.dumps([{"id": "trabalho", "jid": jid, "janela_brt": "22:00"}]),
        })
        self.assertEqual([d.identificador for d in destinos], ["grupo", "trabalho"])
        self.assertTrue(destinos[1].elegivel(datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc)))
        self.assertFalse(destinos[1].elegivel(datetime(2026, 9, 15, 0, 50, tzinfo=timezone.utc)))
        self.assertEqual(destinos_do_ambiente({})[0].prefixo, "grupo")

    def test_coleta_unica_estado_isolado_e_destino_fora_da_janela_nao_processado(self):
        canvas = CanvasFalso()
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            momento = datetime(2026, 9, 15, 0, 50, tzinfo=timezone.utc)
            destinos = [
                Destino("grupo", "grupo@g.us", "grupo"),
                Destino("segundo", "segundo@g.us", "destinos/segundo", "22:00"),
            ]
            codigo, relatorios = executar_destinos(
                objetos=objetos, canvas=canvas.cliente(), entrega_ligada=False,
                ponte=None, destinos=destinos, agora=lambda: momento)
            self.assertEqual(codigo, 0)
            self.assertEqual([r["destino"] for r in relatorios], ["grupo"])
            self.assertIsNotNone(objetos.ler("grupo/memoria.json").dados)
            self.assertIsNotNone(objetos.ler("grupo/ultima-rodada.json").dados)
            # cursos + assignments de Mentoria e Computabilidade + announcements:
            # nenhuma segunda coleta por destino
            self.assertEqual(len(canvas.urls), 3)

    def test_destino_adicional_usa_mesmo_horario_do_destino_padrao(self):
        canvas = CanvasFalso()
        with tempfile.TemporaryDirectory() as tmp:
            codigo, relatorios = executar_destinos(
                objetos=ObjetosLocais(Path(tmp)), canvas=canvas.cliente(), entrega_ligada=False,
                ponte=None,
                destinos=[Destino("grupo", "grupo@g.us", "grupo"),
                          Destino("segundo", "segundo@g.us", "destinos/segundo")],
                agora=lambda: datetime(2026, 9, 15, 0, 50, tzinfo=timezone.utc))
            self.assertEqual(codigo, 0)
            self.assertEqual([r["destino"] for r in relatorios], ["grupo", "segundo"])

    def test_outbox_e_message_id_sao_isolados_por_jid(self):
        canvas = CanvasFalso()
        with tempfile.TemporaryDirectory() as tmp:
            objetos = ObjetosLocais(Path(tmp))
            base = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)
            destinos = [Destino("grupo", "grupo@g.us", "grupo"),
                        Destino("segundo", "segundo@g.us", "destinos/segundo")]
            executar_destinos(objetos=objetos, canvas=canvas.cliente(), entrega_ligada=False,
                              ponte=None, destinos=destinos, agora=lambda: base)
            abre = base + timedelta(hours=3)
            canvas.assignments["292184"] = [quiz(7, abre=abre, fecha=abre + timedelta(minutes=15))]
            ponte = PonteFalsa()
            codigo, relatorios = executar_destinos(
                objetos=objetos, canvas=canvas.cliente(), entrega_ligada=True,
                ponte=ponte, destinos=destinos, agora=lambda: base + timedelta(minutes=30))
            self.assertEqual((codigo, len(relatorios), len(ponte.lotes)), (0, 2, 2))
            self.assertIsNotNone(objetos.ler("grupo/outbox.json").dados)
            self.assertIsNotNone(objetos.ler("destinos/segundo/outbox.json").dados)
            self.assertNotEqual(
                json.loads(objetos.ler("grupo/outbox.json").dados)[0]["message_id"],
                json.loads(objetos.ler("destinos/segundo/outbox.json").dados)[0]["message_id"],
            )


if __name__ == "__main__":
    unittest.main()
