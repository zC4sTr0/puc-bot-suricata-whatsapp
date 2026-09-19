import unittest

import suricata.rodada as rodada
import suricata.rodada.execucao as execucao
from suricata.dominio.lotes import MAX_LOTE, agrupar_envios


def _claim(event_id, texto="t"):
    return {"event_id": event_id, "message_id": "m-" + event_id, "texto": texto,
            "attempt_id": 1}


class LotesCompatibilityTests(unittest.TestCase):
    def test_execucao_e_rodada_reexportam_canonical(self):
        self.assertIs(execucao.MAX_LOTE, MAX_LOTE)
        self.assertIs(execucao.agrupar_envios, agrupar_envios)
        self.assertIs(rodada.MAX_LOTE, MAX_LOTE)
        self.assertIs(rodada.agrupar_envios, agrupar_envios)

    def test_menos_de_dois_novos_nao_agrupa(self):
        claims = [_claim("grupo:novo:a"), _claim("grupo:mudou:b:1")]
        envios = agrupar_envios(claims, "jid")
        self.assertEqual(len(envios), 2)
        for claim, envio in zip(claims, envios, strict=True):
            self.assertEqual(envio["claims"], [claim])
            self.assertEqual(envio["event_id"], claim["event_id"])
            self.assertEqual(envio["message_id"], claim["message_id"])

    def test_novos_da_mesma_leva_viram_um_lote_com_id_deterministico(self):
        claims = [_claim("grupo:novo:b"), _claim("grupo:novo:a"), _claim("grupo:novo:c")]
        envios = agrupar_envios(claims, "jid")
        self.assertEqual(len(envios), 1)
        lote = envios[0]
        self.assertTrue(lote["event_id"].startswith("grupo:lote:"))
        self.assertEqual([c["event_id"] for c in lote["claims"]],
                         ["grupo:novo:a", "grupo:novo:b", "grupo:novo:c"])
        # Determinismo: mesma leva, mesmo id.
        de_novo = agrupar_envios(claims, "jid")
        self.assertEqual(de_novo[0]["event_id"], lote["event_id"])
        self.assertEqual(de_novo[0]["message_id"], lote["message_id"])

    def test_lote_respeita_maximo_de_cinco_e_sobra_isolada(self):
        claims = [_claim(f"grupo:novo:{i}") for i in range(6)]
        envios = agrupar_envios(claims, "jid")
        self.assertEqual(len(envios), 2)
        self.assertEqual(len(envios[0]["claims"]), 5)
        # Sobra de 1 vira envio individual (não lote).
        self.assertTrue(envios[1]["event_id"].startswith("grupo:novo:"))
        self.assertEqual(len(envios[1]["claims"]), 1)

    def test_limite_exato_de_cinco_gera_um_lote_unico(self):
        claims = [_claim(f"grupo:novo:{i}") for i in range(5)]
        envios = agrupar_envios(claims, "jid")
        self.assertEqual(len(envios), 1)
        self.assertEqual(len(envios[0]["claims"]), 5)

    def test_nao_novos_mantem_claims_e_mistura_com_lotes(self):
        claims = [_claim("grupo:mudou:x:1"), _claim("grupo:novo:a"),
                  _claim("grupo:novo:b"), _claim("grupo:anuncio:y")]
        envios = agrupar_envios(claims, "jid")
        ids = [e["event_id"] for e in envios]
        self.assertEqual(ids[0].startswith("grupo:lote:"), True)
        self.assertIn("grupo:mudou:x:1", ids)
        self.assertIn("grupo:anuncio:y", ids)
        # Lotes vêm primeiro; não-novos preservam a ordem relativa.
        nao_novos = [i for i in ids if not i.startswith("grupo:lote:")]
        self.assertEqual(nao_novos, ["grupo:mudou:x:1", "grupo:anuncio:y"])

    def test_texto_do_lote_e_combinacao_dos_textos(self):
        claims = [_claim("grupo:novo:a", "Texto A"), _claim("grupo:novo:b", "Texto B")]
        lote = agrupar_envios(claims, "jid")[0]
        self.assertIn("Texto A", lote["texto"])
        self.assertIn("Texto B", lote["texto"])
        self.assertIn("2 surpresas", lote["texto"])


if __name__ == "__main__":
    unittest.main()
