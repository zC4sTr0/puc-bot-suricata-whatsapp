import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from suricata.dominio.relatorio import Relatorio
from suricata.rodada.execucao import (
    _carregar_memoria,
    _executar_entrega,
    _planejar_rodada,
    _publicar_relatorio,
)
from suricata.storage.cas import StorageError


class _Objeto:
    def __init__(self, dados, generation=7):
        self.dados = dados
        self.generation = generation


class _ObjetosFake:
    def __init__(self, dados):
        self._dados = dados
        self.gravados = []

    def ler(self, nome):
        return _Objeto(self._dados)

    def gravar(self, nome, dados, generation=None):
        self.gravados.append((nome, dados, generation))
        return True


class CarregarMemoriaTests(unittest.TestCase):
    def test_memoria_valida_volta_obj_e_dict(self):
        objetos = _ObjetosFake(json.dumps({"itens": {}}, ensure_ascii=False).encode())
        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        resultado = _carregar_memoria(objetos, "grupo/memoria.json", relatorio)
        self.assertIsNotNone(resultado)
        obj, memoria = resultado
        self.assertEqual(memoria, {"itens": {}})
        self.assertEqual(relatorio.estado, "iniciada")

    def test_memoria_vazia_vira_dicionario_vazio(self):
        objetos = _ObjetosFake(None)
        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        _, memoria = _carregar_memoria(objetos, "grupo/memoria.json", relatorio)
        self.assertEqual(memoria, {})

    def test_memoria_corrompida_marca_relatorio_e_nao_avanca(self):
        objetos = _ObjetosFake(b"{nao e json")
        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        self.assertIsNone(_carregar_memoria(objetos, "grupo/memoria.json", relatorio))
        self.assertEqual(relatorio.estado, "memoria_invalida")
        self.assertEqual(relatorio.erro, "memória persistida inválida; rodada não avançada")

    def test_memoria_nao_objeto_e_rejeitada(self):
        objetos = _ObjetosFake(json.dumps([1, 2]).encode())
        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        self.assertIsNone(_carregar_memoria(objetos, "grupo/memoria.json", relatorio))
        self.assertEqual(relatorio.estado, "memoria_invalida")
        self.assertEqual(relatorio.erro,
                         "memória persistida deve ser um objeto JSON; rodada não avançada")


class PublicarRelatorioTests(unittest.TestCase):
    def test_publica_com_geracao_do_read_back(self):
        objetos = _ObjetosFake(None)
        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        _publicar_relatorio(objetos, "grupo/ultima-rodada.json", relatorio)
        nome, dados, generation = objetos.gravados[0]
        self.assertEqual(nome, "grupo/ultima-rodada.json")
        self.assertEqual(generation, 7)
        self.assertEqual(json.loads(dados)["modo"], "sombra")

    def test_falha_de_storage_nao_propaga(self):
        class Falho:
            def ler(self, nome):
                raise StorageError("boom")

        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        _publicar_relatorio(Falho(), "grupo/ultima-rodada.json", relatorio)  # não levanta


class PlanejarRodadaTests(unittest.TestCase):
    AGORA = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)

    def test_memoria_original_nao_e_mutada_pelo_planejamento(self):
        memoria = {"itens": {}}
        coleta = SimpleNamespace(anuncios=None)
        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        eventos, planejada, comprometida = _planejar_rodada(
            [], memoria, self.AGORA, coleta, [], relatorio, entrega_ligada=False)
        self.assertEqual(eventos, [])
        self.assertTrue(relatorio.linha_de_base)
        # Na linha de base com entrega desligada: cópia da memória original
        # apenas com linha_de_base_em promovida (o planejado ganha chaves novas,
        # mas nada disso é consumido sem entrega).
        self.assertIsNot(comprometida, memoria)
        self.assertEqual(comprometida, {"itens": {},
                                        "linha_de_base_em": "2026-09-15T12:00:00+00:00"})
        self.assertEqual(memoria, {"itens": {}})

    def test_sem_linha_de_base_comprometida_e_copia_da_memoria(self):
        memoria = {"itens": {}, "linha_de_base_em": "2026-09-15T00:00:00+00:00"}
        coleta = SimpleNamespace(anuncios=None)
        relatorio = Relatorio(iniciado_em="t", modo="sombra")
        _, planejada, comprometida = _planejar_rodada(
            [], memoria, self.AGORA, coleta, [], relatorio, entrega_ligada=False)
        self.assertFalse(relatorio.linha_de_base)
        self.assertIsNot(comprometida, memoria)
        self.assertEqual(comprometida, memoria)


class ExecutarEntregaTests(unittest.TestCase):
    def test_entrega_sem_grupo_jid_falha_fechada(self):
        relatorio = Relatorio(iniciado_em="t", modo="entrega")
        with self.assertRaises(StorageError):
            _executar_entrega(_ObjetosFake(None), None, None, "grupo/outbox.json",
                              [], [], lambda: None, None, relatorio, {}, {})

    def test_entrega_sem_ponte_falha_fechada(self):
        relatorio = Relatorio(iniciado_em="t", modo="entrega")
        with self.assertRaises(StorageError):
            _executar_entrega(_ObjetosFake(None), None, "120363@g.us", "grupo/outbox.json",
                              [], [], lambda: None, None, relatorio, {}, {})


if __name__ == "__main__":
    unittest.main()
