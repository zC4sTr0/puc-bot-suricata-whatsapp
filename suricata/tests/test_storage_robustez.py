import json
import unittest
import urllib.error
from unittest.mock import Mock

from suricata.storage.cas import StorageError
from suricata.storage.gcs import ObjetosGCS


class _Resposta:
    def __init__(self, status, corpo=b""):
        self.status = status
        self._corpo = corpo

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._corpo


class GCSRobustezTests(unittest.TestCase):
    def test_geracao_inexistente_termina_com_storage_error_bounded(self):
        abrir = Mock(side_effect=[
            _Resposta(200, json.dumps({"generation": "41"}).encode()),
            urllib.error.HTTPError("url", 404, "not found", {}, None),
            _Resposta(200, json.dumps({"generation": "42"}).encode()),
            urllib.error.HTTPError("url", 404, "not found", {}, None),
            _Resposta(200, json.dumps({"generation": "43"}).encode()),
            urllib.error.HTTPError("url", 404, "not found", {}, None),
        ])
        objetos = ObjetosGCS("gs://bucket", token=lambda: "token", abrir=abrir)

        with self.assertRaises(StorageError) as raised:
            objetos.ler("estado.json")

        self.assertIn("geração", str(raised.exception))
        self.assertEqual(abrir.call_count, 6)

    def test_post_nao_e_repetido_apos_erro_de_transporte(self):
        abrir = Mock(side_effect=urllib.error.URLError("conexão encerrada"))
        objetos = ObjetosGCS("gs://bucket", token=lambda: "token", abrir=abrir)

        with self.assertRaises(StorageError):
            objetos.gravar("estado.json", b"{}", generation=None)

        self.assertEqual(abrir.call_count, 1)


if __name__ == "__main__":
    unittest.main()
