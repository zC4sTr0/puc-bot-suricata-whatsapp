"""TDD da camada opcional ``SURICATA_CONFIG`` (config do grupo por arquivo).

Contrato:
- sem ``SURICATA_CONFIG``: comportamento atual (GRUPO_JID/DESTINOS_JSON).
- com ``SURICATA_CONFIG``: destinos do arquivo são a base; env de destino,
  quando presente, SOBREPOÕE (env > arquivo).
- arquivo ausente / JSON inválido / schema inválido → ValueError fail-closed.
- ``lease_minutos`` do arquivo NÃO é aplicado (limitação documentada: o
  ``LEASE_MINUTOS`` é lido no import de ``lease_rodada``; movê-lo seria
  invasivo). A chave é aceita e validada, mas só alimenta a config.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from suricata.rodada.config import destinos_do_ambiente

JID = "120363000000000000@g.us"
JID2 = "120363000000000000-1700000000@g.us"


def _arquivo(dados: object) -> str:
    tmp = tempfile.mkdtemp()
    caminho = Path(tmp) / "config.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return str(caminho)


def _caminho_vazio() -> str:
    return str(Path(tempfile.mkdtemp()) / "ausente.json")


class SemArquivoCompativelTests(unittest.TestCase):
    """Sem SURICATA_CONFIG, comportamento atual byte a byte."""

    def test_legado_grupo_jid(self):
        destinos = destinos_do_ambiente({"SURICATA_GRUPO_JID": JID})
        self.assertEqual([(d.identificador, d.jid, d.prefixo) for d in destinos],
                         [("grupo", JID, "grupo")])

    def test_vazio_mantem_grupo_nulo(self):
        self.assertEqual(destinos_do_ambiente({})[0].prefixo, "grupo")

    def test_destinos_json_mantem_validacoes(self):
        with self.assertRaises(ValueError):
            destinos_do_ambiente({"SURICATA_DESTINOS_JSON": json.dumps(
                [{"id": "x", "jid": "jid-invalido"}])})


class ArquivoSozinhoTests(unittest.TestCase):
    def test_destinos_do_arquivo_sao_a_base(self):
        caminho = _arquivo({"destinos": [{"id": "familia", "jid": JID2},
                                         {"id": "trabalho", "jid": JID, "janela_brt": "22:00"}]})
        destinos = destinos_do_ambiente({"SURICATA_CONFIG": caminho})
        self.assertEqual([d.identificador for d in destinos], ["familia", "trabalho"])
        self.assertEqual([d.prefixo for d in destinos], ["destinos/familia", "destinos/trabalho"])
        self.assertEqual(destinos[0].jid, JID2)

    def test_item_grupo_do_arquivo_vira_jid_legado(self):
        caminho = _arquivo({"destinos": [{"id": "grupo", "jid": JID},
                                         {"id": "x", "jid": JID2}]})
        destinos = destinos_do_ambiente({"SURICATA_CONFIG": caminho})
        self.assertEqual([d.identificador for d in destinos], ["grupo", "x"])
        self.assertEqual(destinos[0].jid, JID)

    def test_arquivo_vazio_de_destinos_e_fail_closed(self):
        caminho = _arquivo({"destinos": []})
        with self.assertRaises(ValueError):
            destinos_do_ambiente({"SURICATA_CONFIG": caminho})


class PrecedenciaEnvSobreArquivoTests(unittest.TestCase):
    def test_env_destinos_json_sobrepoe_arquivo(self):
        caminho = _arquivo({"destinos": [{"id": "familia", "jid": JID2}]})
        destinos = destinos_do_ambiente({
            "SURICATA_CONFIG": caminho,
            "SURICATA_DESTINOS_JSON": json.dumps([{"id": "outro", "jid": JID}]),
        })
        self.assertEqual([d.identificador for d in destinos], ["outro"])

    def test_env_grupo_jid_sobrepoe_grupo_do_arquivo(self):
        caminho = _arquivo({"destinos": [{"id": "grupo", "jid": JID2},
                                         {"id": "x", "jid": JID2}]})
        destinos = destinos_do_ambiente({"SURICATA_CONFIG": caminho,
                                         "SURICATA_GRUPO_JID": JID})
        grupo = next(d for d in destinos if d.identificador == "grupo")
        self.assertEqual(grupo.jid, JID)


class FailClosedTests(unittest.TestCase):
    def test_arquivo_ausente(self):
        with self.assertRaises(ValueError) as ctx:
            destinos_do_ambiente({"SURICATA_CONFIG": _caminho_vazio()})
        self.assertIn("SURICATA_CONFIG", str(ctx.exception))

    def test_json_invalido(self):
        tmp = tempfile.mkdtemp()
        caminho = Path(tmp) / "config.json"
        caminho.write_text("{quebrado", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            destinos_do_ambiente({"SURICATA_CONFIG": str(caminho)})
        self.assertIn("JSON", str(ctx.exception))

    def test_schema_invalido(self):
        for dados in ([], {"destinos": None}, {"destinos": ["x"]},
                      {"outro": []}, {"destinos": [{"id": "x"}]}):
            with self.subTest(dados=dados):
                with self.assertRaises(ValueError) as ctx:
                    destinos_do_ambiente({"SURICATA_CONFIG": _arquivo(dados)})
                self.assertIn("SURICATA_CONFIG", str(ctx.exception))

    def test_destinos_do_arquivo_passam_pelas_validacoes_existentes(self):
        caminho = _arquivo({"destinos": [{"id": "../escape", "jid": JID}]})
        with self.assertRaises(ValueError):
            destinos_do_ambiente({"SURICATA_CONFIG": caminho})
        caminho = _arquivo({"destinos": [{"id": "x", "jid": JID, "janela_brt": "22:07"}]})
        with self.assertRaises(ValueError):
            destinos_do_ambiente({"SURICATA_CONFIG": caminho})


class LeaseMinutosTests(unittest.TestCase):
    def test_lease_minutos_do_arquivo_e_validado_mas_nao_aplicado(self):
        caminho = _arquivo({"destinos": [{"id": "x", "jid": JID}], "lease_minutos": 9})
        self.assertEqual([d.identificador for d in
                          destinos_do_ambiente({"SURICATA_CONFIG": caminho})], ["x"])
        with self.assertRaises(ValueError):
            destinos_do_ambiente({"SURICATA_CONFIG":
                                  _arquivo({"destinos": [{"id": "x", "jid": JID}],
                                            "lease_minutos": 0})})

    def test_lease_runtime_continua_lido_do_ambiente(self):
        self.assertEqual(
            int(os.environ.get("SURICATA_LEASE_MINUTOS", "6")),
            __import__("suricata.storage.lease_rodada", fromlist=["x"]).LEASE_MINUTOS)


if __name__ == "__main__":
    unittest.main()
