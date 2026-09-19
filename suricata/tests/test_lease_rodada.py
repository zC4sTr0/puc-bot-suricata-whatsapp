"""Caracterização do lease ATIVO da rodada (``suricata.storage.lease_rodada``).

Congela o contrato de ``locks/rodada.lock``: CAS por geração, TTL de
``LEASE_MINUTOS`` (padrão 6, lido do ambiente no import), relógio do servidor
(``updated``) com precedência sobre o ``inicio`` do payload e conteúdo sem
data legível abandonado — nunca um lease preso para sempre. Contrato
deliberadamente distinto do lease legado coberto em ``test_lease.py``.
"""
import importlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import suricata.storage.lease_rodada as lease_rodada
from suricata.storage.cas import CASConflict, StorageError
from suricata.storage.gcs import Objeto, ObjetosLocais
from suricata.storage.lease_rodada import LEASE, LEASE_MINUTOS, Lease, _campo_json

AGORA = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


def _gcs_instante(momento: datetime) -> str:
    """Timestamp no formato ``updated`` que o GCS devolve (RFC 3339 com Z)."""
    return momento.isoformat().replace("+00:00", "Z")


class FakeObjetos:
    """Store em memória com o contrato ``ler``/``gravar``/``apagar`` do lease."""

    def __init__(self, dados=None, generation="1", atualizado_em=None,
                 apagar_resultado=True, levantar_apagar=False, conflito_gravar=False):
        self.dados = dados
        self.generation = generation
        self.atualizado_em = atualizado_em
        self.apagar_resultado = apagar_resultado
        self.levantar_apagar = levantar_apagar
        self.conflito_gravar = conflito_gravar
        self.chamadas = []

    def ler(self, nome):
        self.chamadas.append(("ler", nome))
        if self.dados is None:
            return Objeto(None, None)
        return Objeto(self.dados, self.generation, self.atualizado_em)

    def gravar(self, nome, dados, *, generation, tipo="application/json"):
        self.chamadas.append(("gravar", nome, generation))
        if self.conflito_gravar:
            raise CASConflict("conflito de geração simulado")
        self.dados = dados
        self.generation = "2"
        self.atualizado_em = None
        return "2"

    def apagar(self, nome, *, generation):
        self.chamadas.append(("apagar", nome, generation))
        if self.levantar_apagar:
            raise StorageError("armazenamento indisponível")
        if not self.apagar_resultado or self.dados is None or generation != self.generation:
            return False
        self.dados = None
        self.generation = None
        self.atualizado_em = None
        return True

    def operacoes(self):
        return [chamada[0] for chamada in self.chamadas]


class ConstantesLeaseRodadaTests(unittest.TestCase):
    @unittest.skipIf("SURICATA_LEASE_MINUTOS" in os.environ,
                     "SURICATA_LEASE_MINUTOS sobreposto no ambiente")
    def test_caminho_do_lock_e_ttl_padrao(self):
        self.assertEqual(LEASE, "locks/rodada.lock")
        self.assertEqual(LEASE_MINUTOS, 6)

    def test_ttl_e_lido_do_ambiente_no_import(self):
        try:
            with patch.dict(os.environ, {"SURICATA_LEASE_MINUTOS": "9"}):
                importlib.reload(lease_rodada)
            self.assertEqual(lease_rodada.LEASE_MINUTOS, 9)
        finally:
            importlib.reload(lease_rodada)

    def test_ttl_zero_preserva_o_contrato_da_release(self):
        try:
            with patch.dict(os.environ, {"SURICATA_LEASE_MINUTOS": "0"}):
                importlib.reload(lease_rodada)
            self.assertEqual(lease_rodada.LEASE_MINUTOS, 0)
        finally:
            importlib.reload(lease_rodada)

    def test_ttl_invalido_falha_fechado_no_import(self):
        try:
            for valor in ("-1", "nao-numero"):
                with self.subTest(valor=valor), patch.dict(os.environ, {"SURICATA_LEASE_MINUTOS": valor}):
                    with self.assertRaisesRegex(ValueError, "inteiro não negativo"):
                        importlib.reload(lease_rodada)
        finally:
            importlib.reload(lease_rodada)

    def test_campo_json_ilegivel_devolve_none(self):
        for dados, campo, esperado in (
            (b'{"inicio": "ok"}', "inicio", "ok"),
            (b'{"dono": "x"}', "inicio", None),
            (b"lixo de json", "inicio", None),
            (b'"texto solto"', "campo", None),
        ):
            with self.subTest(dados=dados):
                self.assertEqual(_campo_json(dados, campo), esperado)


class AquisicaoLeaseRodadaTests(unittest.TestCase):
    def test_lock_livre_e_adquirido_com_payload_dono_e_inicio(self):
        store = FakeObjetos()
        lease = Lease(store, agora=lambda: AGORA)
        self.assertTrue(lease.adquirir())
        self.assertEqual(store.operacoes(), ["ler", "gravar"])
        self.assertEqual(store.chamadas[0], ("ler", LEASE))
        self.assertEqual(store.chamadas[1], ("gravar", LEASE, None))
        gravado = json.loads(store.dados)
        self.assertEqual(gravado["inicio"], AGORA.isoformat())
        self.assertEqual(len(gravado["dono"]), 32)  # uuid4().hex
        self.assertEqual(lease.generation, "2")

    def test_ttl_exato_de_lease_minutos_mantem_ocupado(self):
        atualizado = _gcs_instante(AGORA - timedelta(minutes=LEASE_MINUTOS))
        store = FakeObjetos(dados=b'{"dono": "outro", "inicio": "x"}',
                            generation="1", atualizado_em=atualizado)
        lease = Lease(store, agora=lambda: AGORA)
        self.assertFalse(lease.adquirir())
        # ocupado: nenhuma tentativa de apagar ou gravar
        self.assertEqual(store.operacoes(), ["ler"])
        self.assertIsNone(lease.generation)

    def test_ttl_de_lease_minutos_mais_um_segundo_expira_e_readquire(self):
        atualizado = _gcs_instante(AGORA - timedelta(minutes=LEASE_MINUTOS, seconds=1))
        store = FakeObjetos(dados=b'{"dono": "outro", "inicio": "x"}',
                            generation="1", atualizado_em=atualizado)
        lease = Lease(store, agora=lambda: AGORA)
        self.assertTrue(lease.adquirir())
        self.assertEqual(store.operacoes(), ["ler", "apagar", "gravar"])
        self.assertEqual(store.chamadas[1], ("apagar", LEASE, "1"))
        self.assertEqual(store.chamadas[2], ("gravar", LEASE, None))
        self.assertEqual(lease.generation, "2")

    def test_relogio_do_servidor_tem_precedencia_sobre_inicio_do_payload(self):
        # ``updated`` recente + ``inicio`` antigo: o servidor vence e fica ocupado.
        atualizado = _gcs_instante(AGORA - timedelta(minutes=1))
        payload = json.dumps({"dono": "outro",
                              "inicio": (AGORA - timedelta(hours=1)).isoformat()}).encode()
        store = FakeObjetos(dados=payload, generation="1", atualizado_em=atualizado)
        lease = Lease(store, agora=lambda: AGORA)
        self.assertFalse(lease.adquirir())
        self.assertEqual(store.operacoes(), ["ler"])

    def test_inicio_do_payload_e_usado_quando_updated_e_ilegivel(self):
        payload = json.dumps({"dono": "outro",
                              "inicio": (AGORA - timedelta(minutes=1)).isoformat()}).encode()
        store = FakeObjetos(dados=payload, generation="1", atualizado_em="nao-e-data")
        lease = Lease(store, agora=lambda: AGORA)
        self.assertFalse(lease.adquirir())
        self.assertEqual(store.operacoes(), ["ler"])

    def test_payload_sem_data_legivel_e_abandonado_fail_closed(self):
        # Conteúdo corrompido nunca prende o lease: sem data legível, abandonado.
        for dados in (
            b'{"dono": "outro", "inicio": "not-a-date"}',
            b"lixo de json",
            b'{"dono": "outro"}',
            b'{"inicio": 123}',
        ):
            with self.subTest(dados=dados):
                store = FakeObjetos(dados=dados, generation="1", atualizado_em=None)
                lease = Lease(store, agora=lambda: AGORA)
                self.assertTrue(lease.adquirir())
                self.assertEqual(store.operacoes(), ["ler", "apagar", "gravar"])

    def test_abandono_que_perde_a_corrida_de_apagar_devolve_falso(self):
        atualizado = _gcs_instante(AGORA - timedelta(minutes=LEASE_MINUTOS, seconds=1))
        store = FakeObjetos(dados=b'{"dono": "outro"}', generation="1",
                            atualizado_em=atualizado, apagar_resultado=False)
        lease = Lease(store, agora=lambda: AGORA)
        self.assertFalse(lease.adquirir())
        self.assertEqual(store.operacoes(), ["ler", "apagar"])
        self.assertIsNone(lease.generation)

    def test_conflito_cas_na_criacao_devolve_falso(self):
        store = FakeObjetos(conflito_gravar=True)
        lease = Lease(store, agora=lambda: AGORA)
        self.assertFalse(lease.adquirir())
        self.assertEqual(store.operacoes(), ["ler", "gravar"])
        self.assertIsNone(lease.generation)


class LiberarLeaseRodadaTests(unittest.TestCase):
    def test_liberar_sem_ter_adquirido_nao_toca_na_store(self):
        store = FakeObjetos()
        lease = Lease(store, agora=lambda: AGORA)
        lease.liberar()
        self.assertEqual(store.chamadas, [])
        self.assertIsNone(lease.generation)

    def test_liberar_apaga_o_lock_com_a_geracao_do_proprio_dono(self):
        store = FakeObjetos()
        lease = Lease(store, agora=lambda: AGORA)
        self.assertTrue(lease.adquirir())
        lease.liberar()
        self.assertEqual(store.operacoes(), ["ler", "gravar", "apagar"])
        self.assertEqual(store.chamadas[2], ("apagar", LEASE, "2"))
        self.assertIsNone(store.dados)
        self.assertIsNone(lease.generation)
        # segunda liberação é no-op: a geração já foi consumida
        lease.liberar()
        self.assertEqual(len(store.chamadas), 3)

    def test_liberar_de_geracao_suplantada_nao_apaga_lock_alheio(self):
        store = FakeObjetos()
        lease = Lease(store, agora=lambda: AGORA)
        self.assertTrue(lease.adquirir())
        # outro worker assumiu o lock expirado: geração mudou por baixo
        store.generation = "99"
        store.dados = b'{"dono": "outro", "inicio": "depois"}'
        lease.liberar()
        self.assertEqual(store.chamadas[2], ("apagar", LEASE, "2"))
        self.assertEqual(store.dados, b'{"dono": "outro", "inicio": "depois"}')
        self.assertIsNone(lease.generation)

    def test_liberar_reseta_geracao_mesmo_se_apagar_falhar(self):
        store = FakeObjetos(levantar_apagar=True)
        lease = Lease(store, agora=lambda: AGORA)
        self.assertTrue(lease.adquirir())
        with self.assertRaises(StorageError):
            lease.liberar()
        self.assertIsNone(lease.generation)


class CaminhoRealLeaseRodadaTests(unittest.TestCase):
    def test_ciclo_completo_com_objetos_locais(self):
        with tempfile.TemporaryDirectory() as pasta:
            objetos = ObjetosLocais(Path(pasta))
            agora_viva = lambda: datetime.now(timezone.utc)  # noqa: E731
            lease = Lease(objetos, agora=agora_viva)

            self.assertTrue(lease.adquirir())
            lock = Path(pasta) / "locks" / "rodada.lock"
            self.assertTrue(lock.exists())
            gravado = json.loads(lock.read_bytes())
            self.assertIn("dono", gravado)
            datetime.fromisoformat(gravado["inicio"])

            # TTL não decorrido: outro worker não adquire o mesmo lock
            concorrente = Lease(objetos, agora=agora_viva)
            self.assertFalse(concorrente.adquirir())

            lease.liberar()
            self.assertFalse(lock.exists())
            self.assertFalse(lock.with_name(lock.name + ".gen").exists())

            # lock livre de novo: nova aquisição via store local de verdade
            self.assertTrue(Lease(objetos, agora=agora_viva).adquirir())


if __name__ == "__main__":
    unittest.main()
