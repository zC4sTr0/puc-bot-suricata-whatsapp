import os
import unittest
from unittest.mock import patch

from suricata.storage.cas import StorageError
from suricata.storage.gcs import ObjetosLocais
from suricata.storage.sessao import SessaoWhatsApp


class SessionNamespaceTests(unittest.TestCase):
    def test_local_backend_keeps_compatible_relative_session_name(self):
        with patch.dict(os.environ, {}, clear=True):
            session = SessaoWhatsApp(ObjetosLocais("."))
        self.assertEqual(session.nome, "whatsapp/auth.json")

    def test_gcs_explicit_object_must_match_state_namespace(self):
        class FakeGcs:
            bucket = "suricata-state"
            prefixo = "production"

        with patch.dict(os.environ, {"SURICATA_WA_SESSION_OBJECT":
                                     "gs://suricata-state/production/whatsapp/auth.json"}, clear=True):
            session = SessaoWhatsApp(FakeGcs())
        self.assertEqual(session.nome, "whatsapp/auth.json")

    def test_gcs_object_from_another_bucket_fails_closed(self):
        class FakeGcs:
            bucket = "suricata-state"
            prefixo = "production"

        with patch.dict(os.environ, {"SURICATA_WA_SESSION_OBJECT":
                                     "gs://other-product/production/whatsapp/auth.json"}, clear=True):
            with self.assertRaisesRegex(StorageError, "fora do namespace"):
                SessaoWhatsApp(FakeGcs())

    def test_explicit_object_without_gcs_backend_fails_closed(self):
        with patch.dict(os.environ, {"SURICATA_WA_SESSION_OBJECT":
                                     "gs://suricata-state/whatsapp/auth.json"}, clear=True):
            with self.assertRaisesRegex(StorageError, "backend GCS"):
                SessaoWhatsApp(ObjetosLocais("."))


if __name__ == "__main__":
    unittest.main()
