import tempfile
import unittest
from pathlib import Path

import suricata.storage.gcs as gcs
from suricata.storage import _comum, objetos_gcs, objetos_locais, sessao, token
from suricata.storage.cas import AuthSnapshot, CASConflict, ReadBackError, StorageError


class StorageCompatibilityTests(unittest.TestCase):
    def test_facade_reexporta_simbolos_com_identidade(self):
        # Cada símbolo público do gcs histórico é o MESMO objeto do módulo novo.
        self.assertIs(gcs.Objeto, _comum.Objeto)
        self.assertIs(gcs.TokenGCP, token.TokenGCP)
        self.assertIs(gcs.METADATA_TOKEN_URL, token.METADATA_TOKEN_URL)
        self.assertIs(gcs.ObjetosGCS, objetos_gcs.ObjetosGCS)
        self.assertIs(gcs.ObjetosLocais, objetos_locais.ObjetosLocais)
        self.assertIs(gcs.SessaoWhatsApp, sessao.SessaoWhatsApp)

    def test_erros_e_tipos_reexportados_da_cas_tem_identidade(self):
        # Antes da decomposição estes nomes eram atributos de gcs (via import
        # de cas): a fachada precisa continuar devolvendo os mesmos objetos.
        self.assertIs(gcs.StorageError, StorageError)
        self.assertIs(gcs.CASConflict, CASConflict)
        self.assertIs(gcs.ReadBackError, ReadBackError)
        self.assertIs(gcs.AuthSnapshot, AuthSnapshot)

    def test_construir_objetos_continua_definido_na_facade(self):
        # A fábrica depende dos DOIS backends e ficou na raiz de composição
        # (o pacote storage não tem __init__.py); congelamos essa casa.
        self.assertEqual(gcs.construir_objetos.__module__, "suricata.storage.gcs")

    def test_construir_objetos_uri_local_vira_objetos_locais(self):
        with tempfile.TemporaryDirectory() as raiz:
            objetos = gcs.construir_objetos(raiz)
            self.assertIsInstance(objetos, objetos_locais.ObjetosLocais)
            self.assertEqual(objetos.raiz, Path(raiz))

    def test_construir_objetos_uri_gs_vira_objetos_gcs(self):
        objetos = gcs.construir_objetos("gs://bucket/sombra")
        self.assertIsInstance(objetos, objetos_gcs.ObjetosGCS)
        self.assertEqual(objetos.bucket, "bucket")
        self.assertEqual(objetos.prefixo, "sombra")

    def test_construir_objetos_gs_sem_bucket_falha_controlada(self):
        with self.assertRaises(ValueError):
            gcs.construir_objetos("gs://")

    def test_simbolos_usados_pelos_importadores_continuam_importaveis(self):
        # Produção: demo.py (ObjetosLocais); grupos.py, rodada.py e
        # teste_envio.py (SessaoWhatsApp, construir_objetos). Testes:
        # test_lease_rodada.py (Objeto, ObjetosLocais) e
        # test_storage_robustez.py (ObjetosGCS), entre outros.
        from suricata.storage.gcs import (  # noqa: F401
            Objeto,
            ObjetosGCS,
            ObjetosLocais,
            SessaoWhatsApp,
            construir_objetos,
        )
        self.assertIs(Objeto, _comum.Objeto)
        self.assertIs(ObjetosGCS, objetos_gcs.ObjetosGCS)
        self.assertIs(ObjetosLocais, objetos_locais.ObjetosLocais)
        self.assertIs(SessaoWhatsApp, sessao.SessaoWhatsApp)
        self.assertIs(construir_objetos, gcs.construir_objetos)

    def test_sessao_whatsapp_via_facade_roundtrip_cas(self):
        with tempfile.TemporaryDirectory() as raiz:
            sessao_whats = gcs.SessaoWhatsApp(gcs.construir_objetos(raiz))
            vazio = sessao_whats.read_auth()
            self.assertIsNone(vazio.value)
            self.assertIsNone(vazio.generation)
            valor = {"creds": "x"}
            foto = sessao_whats.write_auth(valor, expected_generation=None)
            self.assertEqual(foto.value, valor)
            self.assertEqual(foto.generation, "1")
            # Escrita com geração velha levanta a MESMA exceção de cas.
            with self.assertRaises(CASConflict) as contexto:
                sessao_whats.write_auth(valor, expected_generation=None)
            self.assertIs(type(contexto.exception), CASConflict)


if __name__ == "__main__":
    unittest.main()
