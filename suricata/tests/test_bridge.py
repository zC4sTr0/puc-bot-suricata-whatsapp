import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from suricata.bridge import BridgeError, WhatsAppBridge
from suricata.storage.cas import AuthSnapshot


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.storage = Mock()
        self.storage.read_auth.return_value = AuthSnapshot({"creds.json": "{}"}, "7")
        self.script = Path("C:/Temp/suricata/enviar.mjs")

    @staticmethod
    def completed(payload, returncode=0):
        return Mock(stdout=json.dumps(payload).encode(), stderr=b"secret=must-not-leak", returncode=returncode)

    def test_sessao_ausente_nao_inicia_subprocesso(self):
        self.storage.read_auth.return_value = AuthSnapshot(None, None)
        run = Mock()
        resultado = WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote("1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}])
        self.assertEqual(resultado, {"sessao": "ausente", "resultados": []})
        run.assert_not_called()

    def test_timeout_nao_vaza_stderr(self):
        run = Mock(side_effect=subprocess.TimeoutExpired(["node", "enviar.mjs"], 1))
        with self.assertRaises(BridgeError) as raised:
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote("1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}])
        self.assertEqual(str(raised.exception), "falha ou timeout no processo WhatsApp")
        self.assertNotIn("secret", str(raised.exception))

    def test_ack_falso_em_sessao_ok_e_rejeitado_com_falha_sanitizada(self):
        run = Mock(return_value=self.completed({"sessao": "ok", "resultados": [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "ack": False, "timeout": True, "erro": None}]}))
        with self.assertRaisesRegex(BridgeError, "resposta de sucesso inconsistente"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote("1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}])
        self.storage.write_auth.assert_not_called()

    def test_resposta_ok_vazia_e_rejeitada_com_falha_sanitizada(self):
        run = Mock(return_value=self.completed({"sessao": "ok", "resultados": []}))
        with self.assertRaisesRegex(BridgeError, "resposta de sucesso inconsistente"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}]
            )

    def test_resposta_ok_estrangeira_e_rejeitada_com_falha_sanitizada(self):
        run = Mock(return_value=self.completed({
            "sessao": "ok",
            "resultados": [{"event_id": "outro", "message_id": "3EB040666CAAA98A84571A", "ack": True, "status": 2}],
        }))
        with self.assertRaisesRegex(BridgeError, "resposta de sucesso inconsistente"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}]
            )

    def test_resposta_ok_com_status_invalido_e_rejeitada_com_falha_sanitizada(self):
        run = Mock(return_value=self.completed({
            "sessao": "ok",
            "resultados": [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "ack": True, "status": True}],
        }))
        with self.assertRaisesRegex(BridgeError, "resposta de sucesso inconsistente"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}]
            )

    def test_resposta_ok_com_message_id_divergente_e_rejeitada(self):
        run = Mock(return_value=self.completed({
            "sessao": "ok",
            "resultados": [{"event_id": "e", "message_id": "3EB0FFFFFFFFFFFFFFFF", "ack": True, "status": 2}],
        }))
        with self.assertRaisesRegex(BridgeError, "resposta de sucesso inconsistente"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}]
            )

    def test_resposta_ok_persiste_somente_se_sessao_mudou(self):
        def fake_run(argv, **kwargs):
            auth_dir = Path(json.loads(kwargs["input"])["auth_dir"])
            (auth_dir / "creds.json").write_text('{"updated":true}', encoding="utf-8")
            return self.completed({"sessao": "ok", "resultados": [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "ack": True, "status": 2, "timeout": False, "erro": None}]})

        resultado = WhatsAppBridge(self.storage, script=self.script, run=fake_run).enviar_lote("1-2@g.us", [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}])
        self.assertEqual(resultado["sessao"], "ok")
        self.storage.write_auth.assert_called_once_with({"creds.json": '{"updated":true}'}, expected_generation="7")

    def test_subprocesso_recebe_ambiente_minimo_sem_segredos_herdados(self):
        run = Mock(return_value=self.completed({
            "sessao": "ok",
            "resultados": [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "ack": True, "status": 2}],
        }))
        segredos = {
            "SURICATA_CANVAS_TOKEN": "token-de-teste",
            "SURICATA_WA_AUTH_DIR": "C:/auth-herdado",
            "GCP_SERVICE_ACCOUNT_JSON": "credencial-de-teste",
            "TELEGRAM_BOT_TOKEN": "telegram-de-teste",
            "COOKIE_DE_SESSAO": "cookie-de-teste",
            "NODE_OPTIONS": "--require=modulo-de-teste",
        }

        with patch.dict(os.environ, segredos, clear=False):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us",
                [{"event_id": "e", "message_id": "3EB040666CAAA98A84571A", "texto": "x"}],
            )

        child_env = run.call_args.kwargs["env"]
        self.assertEqual(child_env, {"PATH": os.environ.get("PATH", "")})
        for segredo in segredos:
            self.assertNotIn(segredo, child_env)

    def test_evento_nao_mapping_e_rejeitado_antes_do_subprocesso(self):
        run = Mock()
        with self.assertRaisesRegex(BridgeError, "eventos inválidos"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us", ["evento inválido"]
            )
        run.assert_not_called()

    def test_evento_sem_campo_obrigatorio_e_rejeitado_sem_keyerror(self):
        run = Mock()
        with self.assertRaisesRegex(BridgeError, "eventos inválidos"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us", [{"event_id": "e", "texto": "x"}]
            )
        run.assert_not_called()

    def test_identificador_message_id_nao_deterministico_e_rejeitado(self):
        run = Mock()
        with self.assertRaisesRegex(BridgeError, "eventos inválidos"):
            WhatsAppBridge(self.storage, script=self.script, run=run).enviar_lote(
                "1-2@g.us",
                [{"event_id": "e", "message_id": "não-determinístico", "texto": "x"}],
            )
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
