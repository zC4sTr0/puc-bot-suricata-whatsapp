import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from suricata.notifiers import WhatsAppGrupo, entregar_grupo
from suricata.domain import EventoPublico
from suricata.outbox import Outbox
from suricata.storage.cas import CASConflict


class WhatsAppNotifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "grupo" / "outbox.json"
        self.outbox = Outbox(self.path)
        self.evento = {"event_id": "quiz:42", "texto": "Novo aviso público"}
        self.bridge = Mock()
        self.notificador = WhatsAppGrupo(
            armazenamento=Mock(), grupo_jid="turma@g.us", bridge=self.bridge
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_ack_verdadeiro_persiste_sent_e_message_id_deterministico(self):
        self.bridge.enviar_lote.return_value = {
            "sessao": "ok",
            "resultados": [{"event_id": "quiz:42", "message_id": "3EB0BF0B64C75517FCF51D", "ack": True, "status": 2}],
        }

        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])

        self.assertEqual(resultado[0]["estado"], "sent")
        self.assertEqual(resultado[0]["message_id"], "3EB0BF0B64C75517FCF51D")
        enviado = self.bridge.enviar_lote.call_args.args[1]
        self.assertEqual(enviado[0]["message_id"], resultado[0]["message_id"])
        self.assertEqual(Outbox(self.path)._eventos["quiz:42"]["estado"], "sent")

    def test_sessao_ausente_mantem_pending_sem_chamada_node(self):
        self.bridge.enviar_lote.return_value = {"sessao": "ausente", "resultados": []}

        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])

        self.assertEqual(resultado[0]["estado"], "pending")
        self.assertEqual(self.outbox.pendentes()[0]["estado"], "pending")

    def test_ack_falso_timeout_mantem_pending_e_nunca_sent(self):
        self.bridge.enviar_lote.return_value = {
            "sessao": "timeout",
            "resultados": [
                {"event_id": "quiz:42", "ack": False, "status": None, "timeout": True,
                 "erro": "resposta com segredo que não deve vazar"}
            ],
        }

        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])

        self.assertEqual(resultado[0]["estado"], "pending")
        self.assertNotEqual(resultado[0]["estado"], "sent")
        self.assertLessEqual(len(resultado[0].get("erro", "")), 200)

    def test_conflito_cas_vira_erro_sanitizado_e_pending(self):
        self.bridge.enviar_lote.side_effect = CASConflict("secret-generation-details")

        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])

        self.assertEqual(resultado[0]["estado"], "pending")
        self.assertEqual(resultado[0]["erro"], "sessão WhatsApp alterada por outro processo")
        self.assertNotIn("secret", json.dumps(resultado))
        self.assertLessEqual(len(resultado[0]["erro"]), 200)

    def test_ack_com_status_baixo_nao_e_sent(self):
        self.bridge.enviar_lote.return_value = {
            "sessao": "ok",
            "resultados": [{"event_id": "quiz:42", "ack": True, "status": 1}],
        }

        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])

        self.assertEqual(resultado[0]["estado"], "pending")

    def test_ack_com_sessao_diferente_de_ok_nao_e_sent(self):
        self.bridge.enviar_lote.return_value = {
            "sessao": "timeout",
            "resultados": [{"event_id": "quiz:42", "message_id": "3EB0BF0B64C75517FCF51D", "ack": True, "status": 2}],
        }
        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])
        self.assertEqual(resultado[0]["estado"], "pending")

    def test_ack_com_message_id_divergente_nao_e_sent(self):
        self.bridge.enviar_lote.return_value = {
            "sessao": "ok",
            "resultados": [{"event_id": "quiz:42", "message_id": "ID-DE-OUTRO-EVENTO", "ack": True, "status": 2}],
        }
        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])
        self.assertEqual(resultado[0]["estado"], "pending")

    def test_resultados_duplicados_nao_sao_reduzidos_e_nao_confirmam(self):
        item = {"event_id": "quiz:42", "message_id": "3EB0BF0B64C75517FCF51D", "ack": True, "status": 2}
        self.bridge.enviar_lote.return_value = {"sessao": "ok", "resultados": [item, item.copy()]}
        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])
        self.assertEqual(resultado[0]["estado"], "pending")
        self.assertIn("duplicado", resultado[0]["erro"])

    def test_resultado_extra_nao_e_ignorado_e_nao_confirma(self):
        self.bridge.enviar_lote.return_value = {
            "sessao": "ok",
            "resultados": [
                {"event_id": "quiz:42", "message_id": "3EB0BF0B64C75517FCF51D", "ack": True, "status": 2},
                {"event_id": "evento-extra", "message_id": "ID-EXTRA", "ack": True, "status": 2},
            ],
        }
        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])
        self.assertEqual(resultado[0]["estado"], "pending")
        self.assertIn("extra", resultado[0]["erro"])

    def test_resultado_ausente_e_detectado(self):
        self.bridge.enviar_lote.return_value = {"sessao": "ok", "resultados": []}
        resultado = entregar_grupo(self.outbox, self.notificador, [self.evento])
        self.assertEqual(resultado[0]["estado"], "pending")
        self.assertIn("ausente", resultado[0]["erro"])

    def test_payload_cru_com_situacao_e_rejeitado_antes_do_bridge(self):
        evento = {"event_id": "quiz:privado", "texto": "Situação: entregue", "nota": 10}

        with self.assertRaises(ValueError):
            self.notificador.enviar_lote([evento])

        self.bridge.enviar_lote.assert_not_called()

    def test_payload_aninhado_com_entregue_e_rejeitado_antes_do_bridge(self):
        evento = {
            "event_id": "quiz:aninhado",
            "texto": "aviso",
            "metadata": {"estado": "entregue", "detalhes": {"nota": 10}},
        }

        with self.assertRaises(ValueError):
            self.notificador.enviar_lote([evento])

        self.bridge.enviar_lote.assert_not_called()

    def test_evento_publico_normalizado_e_renderizado_antes_do_bridge(self):
        evento = EventoPublico(
            event_id="quiz:publico",
            curso="Ciência de Dados",
            titulo="Quiz de álgebra",
            tipo="quiz",
        )
        self.bridge.enviar_lote.return_value = {"sessao": "ausente", "resultados": []}

        self.notificador.enviar_lote([evento])

        enviado = self.bridge.enviar_lote.call_args.args[1][0]
        self.assertIn("QUIZ NOVO", enviado["texto"])
        self.assertNotIn("nota", enviado["texto"].casefold())

    def test_entrega_nao_acessa_gravacao_ou_estado_privado_do_outbox(self):
        import inspect
        from suricata.notifiers import whatsapp

        codigo = inspect.getsource(whatsapp.entregar_grupo)
        self.assertNotIn("_eventos", codigo)
        self.assertNotIn("_gravar", codigo)


if __name__ == "__main__":
    unittest.main()
