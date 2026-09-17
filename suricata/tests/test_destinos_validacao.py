"""Validação de destinos antes do carregamento da configuração."""
from __future__ import annotations

import json
import unittest

from suricata.rodada import destinos_do_ambiente


class DestinosValidacaoTests(unittest.TestCase):
    def test_aceita_jids_de_grupo_documentados_e_preserva_configuracao(self):
        destinos = destinos_do_ambiente({
            "SURICATA_GRUPO_JID": "120363000000000000@g.us",
            "SURICATA_DESTINOS_JSON": json.dumps([
                {"id": "turma", "jid": "120363000000000000-1700000000@g.us", "janela_brt": "09:20"},
            ]),
        })

        self.assertEqual([destino.identificador for destino in destinos], ["grupo", "turma"])
        self.assertEqual(destinos[0].jid, "120363000000000000@g.us")
        self.assertEqual(destinos[0].prefixo, "grupo")
        self.assertEqual(destinos[1].jid, "120363000000000000-1700000000@g.us")
        self.assertEqual(destinos[1].prefixo, "destinos/turma")
        self.assertEqual(destinos[1].janela_brt, "09:20")

    def test_rejeita_jid_que_a_ponte_node_rejeitaria(self):
        invalidos = (
            "grupo@g.us",
            "120363000000000000-@g.us",
            "120363000000000000-1700000000-2@g.us",
            "120363000000000000@s.whatsapp.net",
            " 120363000000000000@g.us",
            "120363000000000000@g.us ",
            "١٢@g.us",
        )

        for jid in invalidos:
            with self.subTest(jid=jid):
                with self.assertRaisesRegex(ValueError, r"^JID de destino inválido$"):
                    destinos_do_ambiente({
                        "SURICATA_GRUPO_JID": jid,
                    })

    def test_mensagem_sanitizada_e_janela_continuam_iguais_em_erro(self):
        casos = (
            ({"SURICATA_GRUPO_JID": "nao-e-jid"}, "JID de destino inválido"),
            ({
                "SURICATA_DESTINOS_JSON": json.dumps([
                    {"id": "turma", "jid": "nao-e-jid", "janela_brt": "09:20"},
                ]),
            }, "JID de destino inválido"),
            ({
                "SURICATA_DESTINOS_JSON": json.dumps([
                    {"id": "turma", "jid": "", "janela_brt": "09:20"},
                ]),
            }, "JID de destino ausente"),
            ({
                "SURICATA_DESTINOS_JSON": json.dumps([
                    {"id": "turma", "jid": "120@g.us", "janela_brt": "09:21"},
                ]),
            }, "janela_brt incompatível com Scheduler de 10 minutos"),
        )

        for ambiente, mensagem in casos:
            with self.subTest(ambiente=ambiente):
                with self.assertRaisesRegex(ValueError, rf"^{mensagem}$"):
                    destinos_do_ambiente(ambiente)


if __name__ == "__main__":
    unittest.main()
