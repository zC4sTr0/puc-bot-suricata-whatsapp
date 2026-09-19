import json
import threading
import unittest
from unittest.mock import Mock

from suricata.storage.cas import (
    CASConflict,
    StorageError,
    SuricataSessionStorage,
)


class FakeCasBackend:
    """In-memory GCS-like backend; never contacts cloud or gcloud."""

    def __init__(self, value=None, generation=None):
        self.value = value
        self.generation = generation
        self.lock = threading.Lock()
        self.fail_after_mutation = False

    def result(self, stdout=b"", returncode=0, stderr=b""):
        return Mock(stdout=stdout, stderr=stderr, returncode=returncode)

    def run(self, argv, *, input=None, **_kwargs):
        if argv[1:4] == ["storage", "objects", "describe"]:
            with self.lock:
                if self.value is None:
                    return self.result(stderr=b"ERROR: object not found", returncode=1)
                return self.result(
                    json.dumps({"generation": str(self.generation)}).encode()
                )
        if argv[1:3] == ["storage", "cat"]:
            with self.lock:
                if self.value is None:
                    return self.result(stderr=b"ERROR: object not found", returncode=1)
                return self.result(json.dumps(self.value).encode())
        if argv[1:3] == ["storage", "cp"]:
            expected = argv[5].split("=", 1)[1]
            with self.lock:
                actual = "0" if self.value is None else str(self.generation)
                if expected != actual:
                    return self.result(
                        stderr=b"ERROR: 412 precondition failed", returncode=1
                    )
                self.value = json.loads(input.decode())
                self.generation = 1 if self.generation is None else int(self.generation) + 1
                if self.fail_after_mutation:
                    return self.result(
                        stderr=b"ERROR: transport closed after commit", returncode=1
                    )
                return self.result()
        raise AssertionError(argv)


class AdversarialStorageWorkerTests(unittest.TestCase):
    def test_concurrent_writers_only_one_generation_wins(self):
        backend = FakeCasBackend({"version": 0}, 7)
        first = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=backend.run)
        second = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=backend.run)
        first_snapshot = first.read_auth()
        second_snapshot = second.read_auth()

        winner = first.write_auth({"version": 1}, expected_generation=first_snapshot.generation)
        self.assertEqual(winner.generation, "8")
        with self.assertRaises(CASConflict):
            second.write_auth({"version": 2}, expected_generation=second_snapshot.generation)
        self.assertEqual(backend.value, {"version": 1})

    def test_generation_conflict_is_sanitized_and_does_not_leak_payload(self):
        run = Mock(
            return_value=Mock(
                stdout=b"",
                stderr=b"ERROR: 412 precondition failed secret=do-not-leak",
                returncode=1,
            )
        )
        storage = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=run)

        with self.assertRaises(CASConflict) as raised:
            storage.write_auth({"secret": "do-not-leak"}, expected_generation="41")

        self.assertNotIn("do-not-leak", str(raised.exception))

    def test_crash_after_remote_mutation_is_reported_without_retry(self):
        backend = FakeCasBackend({"version": 0}, 3)
        backend.fail_after_mutation = True
        storage = SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=backend.run)

        with self.assertRaises(StorageError):
            storage.write_auth({"version": 1}, expected_generation="3")

        # The caller receives an error although the remote mutation happened;
        # an automatic retry would be unsafe without a read/reconcile policy.
        self.assertEqual(backend.value, {"version": 1})
        self.assertEqual(backend.generation, 4)

    def test_concurrent_read_rejects_mixed_generation_and_payload(self):
        """A describe+cat read rejects an old payload after a concurrent update."""
        class TornReadBackend(FakeCasBackend):
            def run(self, argv, **kwargs):
                if argv[1:3] == ["storage", "cat"]:
                    with self.lock:
                        old_payload = self.result(json.dumps(self.value).encode())
                        self.value = {"version": 2}
                        self.generation = 11
                    # The read started before the update and returns the old
                    # bytes; the final describe must detect the generation
                    # change instead of returning a stale AuthSnapshot.
                    return old_payload
                return super().run(argv, **kwargs)

        backend = TornReadBackend({"version": 1}, 10)
        with self.assertRaises(StorageError) as raised:
            SuricataSessionStorage(session_object="gs://test.invalid/whatsapp/auth.json", run=backend.run).read_auth()
        self.assertEqual(str(raised.exception), "leitura inconsistente da sessão WhatsApp")


if __name__ == "__main__":
    unittest.main()
