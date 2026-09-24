from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from suricata.rodada import OUTBOX, Evento, OutboxSincronizado, entregar, rodape
from suricata.storage.objetos_locais import ObjetosLocais
from suricata.tests._fakes import PonteFalsa

URL = "https://github.com/exemplo/suricata"
NOME = "grupo/outbox.json"
ESTADO = "grupo/rodape.json"


def _meio_dia(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, 15, tzinfo=timezone.utc)  # 12:00 BRT


def _envios():
    return [{"event_id": "a", "message_id": "m1", "texto": "aviso A"},
            {"event_id": "b", "message_id": "m2", "texto": "aviso B"}]


@patch.dict(os.environ, {"SURICATA_REPO_URL": URL})
class TestRodape(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.objetos = ObjetosLocais(self.tmp.name)
        self.inicio = date(2026, 9, 24)

    def tearDown(self):
        self.tmp.cleanup()

    def _estado(self):
        return json.loads(self.objetos.ler(ESTADO).dados)

    def _rodada(self, dia, sem_ack=()):
        envios = _envios()
        contexto = rodape.anexar(self.objetos, NOME, envios, _meio_dia(dia))
        rodape.confirmar(self.objetos, contexto, list(sem_ack))
        return envios

    def test_primeiro_envio_so_marca_inicio(self):
        envios = self._rodada(self.inicio)
        self.assertNotIn(URL, envios[-1]["texto"])
        self.assertEqual(self._estado(), {"inicio": "2026-09-24"})

    def test_agenda_7_21_49_dias_e_depois_para(self):
        self._rodada(self.inicio)
        com_rodape = []
        for d in range(1, 120):
            dia = self.inicio + timedelta(days=d)
            if URL in self._rodada(dia)[-1]["texto"]:
                com_rodape.append(d)
        self.assertEqual(com_rodape, [7, 21, 49])
        self.assertEqual(self._estado()["mostrados"], 3)

    def test_rodape_so_no_ultimo_envio_e_nao_altera_o_original(self):
        self._rodada(self.inicio)
        envios = _envios()
        originais = list(envios)
        rodape.anexar(self.objetos, NOME, envios, _meio_dia(self.inicio + timedelta(days=7)))
        self.assertEqual(envios[0]["texto"], "aviso A")
        self.assertTrue(envios[-1]["texto"].startswith("aviso B\n\n"))
        self.assertTrue(envios[-1]["texto"].endswith(URL))
        self.assertEqual(originais[-1]["texto"], "aviso B")  # registro do outbox intacto
        self.assertEqual(envios[-1]["message_id"], "m2")

    def test_sem_ack_nao_avanca_e_rodape_repete_na_proxima(self):
        self._rodada(self.inicio)
        dia7 = self.inicio + timedelta(days=7)
        self.assertIn(URL, self._rodada(dia7, sem_ack=["b"])[-1]["texto"])
        self.assertNotIn("mostrados", self._estado())
        self.assertIn(URL, self._rodada(dia7)[-1]["texto"])
        self.assertEqual(self._estado()["mostrados"], 1)

    def test_sem_url_nao_ha_rodape_nem_estado(self):
        with patch.dict(os.environ, {"SURICATA_REPO_URL": ""}):
            envios = self._rodada(self.inicio)
        self.assertEqual(envios[-1]["texto"], "aviso B")
        self.assertIsNone(self.objetos.ler(ESTADO).dados)

    def test_url_nao_https_e_ignorada(self):
        with patch.dict(os.environ, {"SURICATA_REPO_URL": "http://x"}):
            self.assertIsNone(rodape.anexar(self.objetos, NOME, _envios(), _meio_dia(self.inicio)))

    def test_falha_de_storage_omite_rodape_sem_derrubar(self):
        objetos = Mock()
        objetos.ler.side_effect = OSError("indisponível")
        envios = _envios()
        self.assertIsNone(rodape.anexar(objetos, NOME, envios, _meio_dia(self.inicio)))
        self.assertEqual(envios[-1]["texto"], "aviso B")

    def test_estado_corrompido_omite_rodape(self):
        self.objetos.gravar(ESTADO, b"{nao-json", generation=None)
        self.assertIsNone(rodape.anexar(self.objetos, NOME, _envios(), _meio_dia(self.inicio)))

    def test_estado_por_destino(self):
        rodape.anexar(self.objetos, "destinos/ti/outbox.json", _envios(), _meio_dia(self.inicio))
        self.assertIsNotNone(self.objetos.ler("destinos/ti/rodape.json").dados)
        self.assertIsNone(self.objetos.ler(ESTADO).dados)

    def test_entregar_envia_rodape_mas_outbox_guarda_texto_original(self):
        self.objetos.gravar(ESTADO, json.dumps({"inicio": "2026-09-17"}).encode(), generation=None)
        ponte = PonteFalsa()
        fila = OutboxSincronizado(self.objetos, Path(self.tmp.name))
        entregar(fila, ponte, "fake@g.us", [Evento("novo", "grupo:novo:x", "aviso X")], _meio_dia(self.inicio))
        self.assertTrue(ponte.lotes[0][-1]["texto"].endswith(URL))
        registro = json.loads(self.objetos.ler(OUTBOX).dados)[0]
        self.assertEqual((registro["texto"], registro["estado"]), ("aviso X", "sent"))
        self.assertEqual(self._estado()["mostrados"], 1)


if __name__ == "__main__":
    unittest.main()
