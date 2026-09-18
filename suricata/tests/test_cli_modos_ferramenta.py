"""Caracterização offline dos modos CLI órfãos ``grupos`` e ``teste-envio``.

Congela apenas a **recusa**/comportamento observado por subprocesso real, sem
estado ou destino configurados. Nenhum caminho aqui inicia o Node/Baileys ou
toca a rede — o subprocesso roda com ``PATH`` vazio como tripwire: qualquer
tentativa de spawn (``node``, ``gcloud``) falharia alto com ``FileNotFoundError``
e derrubaria o teste.

Achados congelados (árvore em ``refactor/clean-architecture-domain-seams``):

* ``--mode grupos``: fail-closed conforme desenhado — exit 5 com
  ``SURICATA_ESTADO_URI`` ausente; exit 6 ``{"sessao": "ausente"}`` quando o
  estado local não tem sessão (o Node nunca é iniciado sem sessão).
* ``--mode teste-envio``: fail-closed conforme desenhado — exit 5 quando
  falta ``SURICATA_ESTADO_URI``/``SURICATA_GRUPO_JID`` (antes de qualquer
  lease, sessão ou ponte); exit 4 ``{"estado": "lease_ocupado"}`` quando o
  lease da rodada já está tomado (o Node/Baileys nunca é iniciado). O modo
  teve um ImportError de ``Lease`` entre dd89264 e a correção canônica do
  import; congelamos as recusas seguras, nunca o envio.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRUPO = "120363000000000000@g.us"


def _env(**suricata):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SURICATA_")}
    # Tripwire: sem PATH, qualquer spawn de subprocesso (node/gcloud) falha alto.
    env["PATH"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(suricata)
    return env


def _rodar(argv, env):
    return subprocess.run(
        [sys.executable, "-m", "suricata", *argv],
        capture_output=True,
        cwd=str(ROOT),
        env=env,
        timeout=180,
        check=False,
    )


def _registro_unico(concluido):
    linhas = concluido.stdout.decode("utf-8").strip().splitlines()
    assert len(linhas) == 1, f"esperava 1 linha de stdout, veio {len(linhas)}: {linhas!r}"
    return json.loads(linhas[0])


class GruposModoTests(unittest.TestCase):
    def test_sem_estado_uri_recusa_com_erro_sanitizado(self):
        concluido = _rodar(["--mode", "grupos"], _env())

        self.assertEqual(concluido.returncode, 5)
        self.assertEqual(concluido.stderr, b"")
        self.assertEqual(_registro_unico(concluido),
                         {"sessao": "erro", "erro": "SURICATA_ESTADO_URI ausente (use um diretório local ou gs://...)"})

    def test_estado_local_sem_sessao_devolve_ausente_sem_iniciar_node(self):
        with tempfile.TemporaryDirectory() as estado:
            concluido = _rodar(["--mode", "grupos"], _env(SURICATA_ESTADO_URI=estado))

            self.assertEqual(concluido.returncode, 6)
            self.assertEqual(concluido.stderr, b"")
            self.assertEqual(_registro_unico(concluido), {"sessao": "ausente", "grupos": []})


class TesteEnvioModoTests(unittest.TestCase):
    """Recusas fail-closed do ``teste_envio``; o envio em si é efeito externo
    proibido em validação e nunca é caracterizado aqui."""

    def test_sem_env_e_destino_recusa_com_erro_sanitizado(self):
        concluido = _rodar(["--mode", "teste-envio"], _env())

        self.assertEqual(concluido.returncode, 5)
        self.assertEqual(concluido.stderr, b"")
        self.assertEqual(_registro_unico(concluido), {
            "estado": "erro",
            "erro": "SURICATA_ESTADO_URI e SURICATA_GRUPO_JID são obrigatórios",
        })

    def test_lease_da_rodada_ocupado_recusa_sem_iniciar_node(self):
        # O lease é tomado ANTES da ponte: com o lock de rodada ocupado, o modo
        # devolve exit 4 sem nunca construir a sessão ou iniciar o Node.
        from suricata.lease_rodada import Lease
        from suricata.storage.gcs import ObjetosLocais

        with tempfile.TemporaryDirectory() as estado:
            objetos = ObjetosLocais(Path(estado))
            dono = Lease(objetos, lambda: datetime.now(timezone.utc))
            self.assertTrue(dono.adquirir())

            concluido = _rodar(
                ["--mode", "teste-envio"],
                _env(SURICATA_ESTADO_URI=estado, SURICATA_GRUPO_JID=GRUPO),
            )

            self.assertEqual(concluido.returncode, 4)
            self.assertEqual(concluido.stderr, b"")
            self.assertEqual(_registro_unico(concluido), {"estado": "lease_ocupado"})


if __name__ == "__main__":
    unittest.main()
