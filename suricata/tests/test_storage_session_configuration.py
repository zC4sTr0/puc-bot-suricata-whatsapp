import os
import subprocess
import unittest
from unittest.mock import Mock, patch

from suricata.storage.cas import StorageError, SuricataSessionStorage


class SessionStorageConfigurationTests(unittest.TestCase):
    @staticmethod
    def result(stdout=b'{"generation":"1"}'):
        return Mock(stdout=stdout, stderr=b"", returncode=0)

    def test_explicit_session_object_is_used_for_every_gcloud_operation(self):
        run = Mock(side_effect=[
            self.result(),
            self.result(b'{"creds.json":"opaque"}'),
            self.result(),
        ])
        storage = SuricataSessionStorage(
            session_object="gs://suricata-prod-state/whatsapp/auth.json",
            run=run,
        )

        storage.read_auth()

        uris = [next(item for item in call.args[0] if item.startswith("gs://")) for call in run.call_args_list]
        self.assertEqual(uris, [
            "gs://suricata-prod-state/whatsapp/auth.json",
            "gs://suricata-prod-state/whatsapp/auth.json",
            "gs://suricata-prod-state/whatsapp/auth.json",
        ])

    def test_environment_session_object_is_used_when_constructor_is_omitted(self):
        run = Mock(side_effect=[self.result(), self.result(b'{"x":"y"}'), self.result()])
        with patch.dict(os.environ, {"SURICATA_WA_SESSION_OBJECT": "gs://suricata-canary-state/wa/auth.json"}, clear=False):
            SuricataSessionStorage(run=run).read_auth()

        self.assertTrue(all(
            any(item == "gs://suricata-canary-state/wa/auth.json" for item in call.args[0])
            for call in run.call_args_list
        ))

    def test_production_without_session_object_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(StorageError, "objeto da sessão WhatsApp ausente"):
                SuricataSessionStorage(run=subprocess.run)

    def test_constructor_and_environment_disagreement_is_ambiguous(self):
        with patch.dict(os.environ, {"SURICATA_WA_SESSION_OBJECT": "gs://other/auth.json"}, clear=False):
            with self.assertRaisesRegex(StorageError, "ambíguo"):
                SuricataSessionStorage(
                    session_object="gs://suricata/auth.json",
                    run=Mock(),
                )


if __name__ == "__main__":
    unittest.main()
