import json
import os
import unittest
from unittest.mock import Mock, patch

from suricata.storage.cas import (
    CASConflict,
    SuricataSessionStorage,
)


class SuricataSessionStorageTests(unittest.TestCase):
    def test_read_auth_returns_object_and_generation_without_network_sdk(self):
        run = Mock(side_effect=[
            self.result('{"generation": "17"}'),
            self.result('{"creds.json": "opaque"}'),
            self.result('{"generation": "17"}'),
        ])
        storage = SuricataSessionStorage(run=run)

        snapshot = storage.read_auth()

        self.assertEqual(snapshot.value, {"creds.json": "opaque"})
        self.assertEqual(snapshot.generation, "17")
        self.assertEqual(run.call_args_list[0].args[0][:4], ["gcloud", "storage", "objects", "describe"])
        self.assertEqual(run.call_args_list[1].args[0][:4], ["gcloud", "storage", "cat", "gs://suricata-college-20260913-estado/whatsapp/auth.json"])

    def test_missing_auth_is_explicit(self):
        run = Mock(return_value=self.result("", returncode=1, stderr="ERROR: object not found"))
        storage = SuricataSessionStorage(run=run)

        snapshot = storage.read_auth()

        self.assertIsNone(snapshot.value)
        self.assertIsNone(snapshot.generation)
        run.assert_called_once()

    def test_write_uses_generation_precondition_and_reads_back(self):
        run = Mock(side_effect=[
            self.result(""),
            self.result('{"generation": "18"}'),
            self.result('{"creds.json": "opaque"}'),
            self.result('{"generation": "18"}'),
        ])
        storage = SuricataSessionStorage(run=run)
        value = {"creds.json": "opaque"}

        snapshot = storage.write_auth(value, expected_generation="17")

        self.assertEqual(snapshot.value, value)
        self.assertEqual(snapshot.generation, "18")
        write_args = run.call_args_list[0].args[0]
        self.assertIn("--if-generation-match=17", write_args)
        self.assertNotIn(json.dumps(value), write_args)
        self.assertEqual(run.call_args_list[0].kwargs["input"], json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())

    def test_create_uses_zero_generation_precondition(self):
        run = Mock(side_effect=[
            self.result(""),
            self.result('{"generation": "1"}'),
            self.result('{"creds.json": "opaque"}'),
            self.result('{"generation": "1"}'),
        ])
        storage = SuricataSessionStorage(run=run)

        storage.write_auth({"creds.json": "opaque"}, expected_generation=None)

        self.assertIn("--if-generation-match=0", run.call_args_list[0].args[0])

    def test_gcloud_recebe_ambiente_minimo_sem_tokens_herdados(self):
        run = Mock(side_effect=[
            self.result('{"generation": "17"}'),
            self.result('{"creds.json": "opaque"}'),
            self.result('{"generation": "17"}'),
        ])
        herdado = {
            "SURICATA_CANVAS_TOKEN": "canvas-secreto",
            "TELEGRAM_BOT_TOKEN": "telegram-secreto",
            "ACADEMICO_BOT_TELEGRAM_TOKEN": "telegram-academico-secreto",
            "GCP_SERVICE_ACCOUNT_JSON": "gcp-secreto",
            "GOOGLE_APPLICATION_CREDENTIALS": "credencial-secreta",
            "CLOUDSDK_AUTH_ACCESS_TOKEN": "access-token-secreto",
            "NODE_OPTIONS": "--require=modulo-nao-permitido",
            "SURICATA_WA_AUTH_DIR": "C:/auth-herdado",
        }

        with patch.dict(os.environ, herdado, clear=False):
            SuricataSessionStorage(run=run).read_auth()

        esperado = {"PATH": os.environ.get("PATH", "")}
        esperado.update({key: os.environ[key] for key in ("HOME", "USERPROFILE", "CLOUDSDK_CONFIG") if key in os.environ})
        for chamada in run.call_args_list:
            self.assertEqual(chamada.kwargs["env"], esperado)
            for nome in herdado:
                self.assertNotIn(nome, chamada.kwargs["env"])

    def test_write_conflict_does_not_expose_session(self):
        run = Mock(return_value=self.result("", returncode=1, stderr="ERROR: 412 precondition failed"))
        storage = SuricataSessionStorage(run=run)

        with self.assertRaises(CASConflict) as raised:
            storage.write_auth({"secret": "must-not-appear"}, expected_generation="17")

        self.assertNotIn("must-not-appear", str(raised.exception))

    @staticmethod
    def result(stdout, returncode=0, stderr=""):
        return Mock(stdout=stdout.encode(), stderr=stderr.encode(), returncode=returncode)


if __name__ == "__main__":
    unittest.main()
