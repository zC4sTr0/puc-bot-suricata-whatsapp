import unittest
from datetime import datetime, timedelta, timezone

from suricata.lease import Lease, LeaseConfig, LeaseState


class FakeLeaseStore:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, key):
        self.calls.append(("GET", key))
        return self.response

    def put_if_absent(self, key, value):
        self.calls.append(("PUT_IF_ABSENT", key, value))
        return True

    def delete_if_owner(self, key, owner):
        self.calls.append(("DELETE", key, owner))
        return True


class LeaseTests(unittest.TestCase):
    def test_default_de_seis_minutos_e_expira_com_sete(self):
        agora = datetime(2026, 9, 13, tzinfo=timezone.utc)
        lease = Lease(FakeLeaseStore(None), now=lambda: agora)
        self.assertEqual(lease.config.minutes, 6)
        self.assertEqual(lease.classify_time(agora - timedelta(minutes=7)), LeaseState.EXPIRED)
        self.assertEqual(lease.classify_time(agora - timedelta(minutes=5)), LeaseState.ACTIVE)

    def test_indisponibilidade_da_store_falha_fechado(self):
        class Broken:
            def get(self, key):
                raise OSError("storage down")
        lease = Lease(Broken())
        with self.assertRaises(RuntimeError):
            lease.acquire()

    def test_payload_malformado_falha_fechado(self):
        lease = Lease(FakeLeaseStore({"started_at": "not-a-date"}))
        with self.assertRaises(RuntimeError):
            lease.acquire()

    def test_lease_ativo_nao_e_adquirido(self):
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        store = FakeLeaseStore({"owner": "other", "started_at": (now - timedelta(minutes=5)).isoformat()})
        lease = Lease(store, now=lambda: now)
        self.assertFalse(lease.acquire())
        self.assertEqual([call[0] for call in store.calls], ["GET"])


if __name__ == "__main__":
    unittest.main()
