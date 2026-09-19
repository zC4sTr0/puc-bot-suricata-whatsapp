import multiprocessing
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from suricata.storage.cas import CASConflict
from suricata.storage.gcs import ObjetosLocais


def _gravar_local_em_processo(raiz, largada, resultados, generation, versao):
    objetos = ObjetosLocais(raiz)
    largada.wait(10)
    try:
        resultados.put(("ok", objetos.gravar("estado.json", f'{{"versao":{versao}}}'.encode(), generation=generation)))
    except CASConflict:
        resultados.put(("cas", None))
    except Exception as exc:  # a asserção do processo rejeita PermissionError e demais falhas
        resultados.put((type(exc).__name__, str(exc)))


def _segurar_lock_local(raiz, pronto):
    objetos = ObjetosLocais(raiz)
    with objetos._trava_objeto("estado.json"):
        pronto.set()
        time.sleep(30)


class ObjetosLocaisConcurrencyTests(unittest.TestCase):
    def test_processos_concorrentes_tem_uma_vitoria_e_um_cas_conflict(self):
        ctx = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            geracao = ObjetosLocais(raiz).gravar("estado.json", b'{"versao":1}', generation=None)
            largada = ctx.Event()
            resultados = ctx.Queue()
            processos = [
                ctx.Process(target=_gravar_local_em_processo, args=(str(raiz), largada, resultados, geracao, versao))
                for versao in (2, 3)
            ]
            for processo in processos:
                processo.start()
            largada.set()
            recebidos = [resultados.get(timeout=15) for _ in processos]
            for processo in processos:
                processo.join(15)
                self.assertEqual(processo.exitcode, 0)
            self.assertEqual(sorted(item[0] for item in recebidos), ["cas", "ok"])
            self.assertEqual(ObjetosLocais(raiz).ler("estado.json").generation, "2")
            self.assertNotIn("PermissionError", str(recebidos))

    def test_processo_morto_libera_lock_local_e_preserva_cas(self):
        ctx = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            objetos = ObjetosLocais(raiz)
            geracao = objetos.gravar("estado.json", b'{"versao":1}', generation=None)
            pronto = ctx.Event()
            processo = ctx.Process(target=_segurar_lock_local, args=(str(raiz), pronto))
            processo.start()
            self.assertTrue(pronto.wait(10))
            processo.terminate()
            processo.join(10)
            self.assertNotEqual(processo.exitcode, 0)
            self.assertEqual(objetos.gravar("estado.json", b'{"versao":2}', generation=geracao), "2")
            self.assertEqual(objetos.ler("estado.json").dados, b'{"versao":2}')

    def test_instancias_concorrentes_vencem_ou_retornam_cas_conflict(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            inicial = ObjetosLocais(raiz)
            geracao = inicial.gravar("estado.json", b'{"versao":1}', generation=None)
            objetos = (ObjetosLocais(raiz), ObjetosLocais(raiz))
            largada = threading.Barrier(2)
            primeira_troca = threading.Event()
            liberar_primeira_troca = threading.Event()
            resultados = []
            erros = []
            real_replace = __import__("os").replace
            primeira = True
            guarda_primeira = threading.Lock()

            def replace_controlado(origem, destino):
                nonlocal primeira
                with guarda_primeira:
                    bloquear = primeira
                    primeira = False
                if bloquear and Path(destino).name == "estado.json":
                    primeira_troca.set()
                    if not liberar_primeira_troca.wait(timeout=5):
                        raise AssertionError("a segunda gravação não alcançou a troca")
                return real_replace(origem, destino)

            def gravar(objetos_locais, dados):
                largada.wait(timeout=5)
                try:
                    resultados.append(objetos_locais.gravar("estado.json", dados, generation=geracao))
                except Exception as exc:  # a asserção abaixo rejeita erros não-CAS
                    erros.append(exc)

            with patch("suricata.storage.gcs.os.replace", side_effect=replace_controlado):
                threads = [
                    threading.Thread(target=gravar, args=(objetos[0], b'{"versao":2}')),
                    threading.Thread(target=gravar, args=(objetos[1], b'{"versao":3}')),
                ]
                for thread in threads:
                    thread.start()
                self.assertTrue(primeira_troca.wait(timeout=5))
                liberar_primeira_troca.set()
                for thread in threads:
                    thread.join(timeout=5)
                    self.assertFalse(thread.is_alive())

            self.assertEqual(sorted(resultados), ["2"])
            self.assertEqual(len(erros), 1)
            self.assertIsInstance(erros[0], CASConflict)
            snapshot = inicial.ler("estado.json")
            self.assertIn(snapshot.dados, (b'{"versao":2}', b'{"versao":3}'))
            self.assertEqual(snapshot.generation, "2")
            self.assertEqual(list(raiz.rglob("*.tmp")), [])
            self.assertEqual(list(raiz.rglob("*.bak")), [])


if __name__ == "__main__":
    unittest.main()
