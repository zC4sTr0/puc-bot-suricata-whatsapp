import json
import unittest
from unittest.mock import Mock

from suricata.storage.cas import StorageError, SuricataSessionStorage


class CasReadRevalidationTests(unittest.TestCase):
    @staticmethod
    def result(stdout=b"", returncode=0, stderr=b""):
        return Mock(stdout=stdout, stderr=stderr, returncode=returncode)

    def test_read_auth_rejects_generation_changed_after_payload_read(self):
        calls = [
            self.result(json.dumps({"generation": "10"}).encode()),
            self.result(json.dumps({"version": 2}).encode()),
            self.result(json.dumps({"generation": "11"}).encode()),
        ]
        run = Mock(side_effect=calls)
        storage = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=run)

        with self.assertRaises(StorageError) as raised:
            storage.read_auth()

        self.assertEqual(run.call_count, 3)
        self.assertNotIn("version", str(raised.exception))
        self.assertNotIn("2", str(raised.exception))

    def test_read_auth_rejects_invalid_payload_without_exposing_it(self):
        run = Mock(side_effect=[
            self.result(b'{"generation":"10"}'),
            self.result(b'{"secret":"not-for-logs"'),
        ])
        storage = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=run)

        with self.assertRaises(StorageError) as raised:
            storage.read_auth()

        self.assertNotIn("not-for-logs", str(raised.exception))

    def test_read_auth_rejects_non_finite_json_constants_without_exposing_payload(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                run = Mock(side_effect=[
                    self.result(b'{"generation":"10"}'),
                    self.result((f'{{"secret":"not-for-logs", "value": {constant}}}').encode()),
                    self.result(b'{"generation":"10"}'),
                ])
                storage = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=run)

                with self.assertRaises(StorageError) as raised:
                    storage.read_auth()

                self.assertNotIn("not-for-logs", str(raised.exception))
                self.assertNotIn(constant, str(raised.exception))

    def test_read_auth_still_accepts_regular_json_values(self):
        run = Mock(side_effect=[
            self.result(b'{"generation":"10"}'),
            self.result(b'{"secret":"opaque", "value": 1.5, "enabled": true, "empty": null}'),
            self.result(b'{"generation":"10"}'),
        ])
        storage = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=run)

        self.assertEqual(
            storage.read_auth().value,
            {"secret": "opaque", "value": 1.5, "enabled": True, "empty": None},
        )


if __name__ == "__main__":
    unittest.main()
