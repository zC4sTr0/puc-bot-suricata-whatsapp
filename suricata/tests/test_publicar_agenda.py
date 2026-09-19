"""Testes de publicar_agenda: validação pura, publicação local e tripwire.

A publicação usa ``SURICATA_ESTADO_URI`` apontando para um diretório
temporário (``ObjetosLocais``), sem rede. O ``--dry-run`` valida e imprime
sem escrever nada; ``--validar`` valida sem publicar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "deploy" / "publicar_agenda.py"
sys.path.insert(0, str(REPO))

from deploy.publicar_agenda import OBJETO, main, validar  # noqa: E402


def item(**cambios: object) -> dict:
    base: dict = {"id": "a1", "tipo": "quiz", "titulo": "Quiz 1",
                  "curso": "Matemática", "curso_id": "mat", "data": None}
    base.update(cambios)
    return base


def agenda(itens: list[dict], classe: str = "nota_pessoal") -> bytes:
    return json.dumps({"classe": classe, "itens": itens}).encode("utf-8")


class ValidacaoPuraTests(unittest.TestCase):
    def test_agenda_valida_nao_tem_erros(self):
        self.assertEqual(validar({"classe": "nota_pessoal", "itens": [item()]}), [])

    def test_classe_errada_e_reportada(self):
        erros = validar({"classe": "outra", "itens": [item()]})
        self.assertTrue(any("nota_pessoal" in e for e in erros), erros)

    def test_id_ausente_e_repetido_sao_reportados(self):
        erros = validar({"classe": "nota_pessoal",
                         "itens": [item(id=None), item(id=None), item(id="dup"), item(id="dup")]})
        self.assertEqual(sum("id ausente ou repetido" in e for e in erros), 3)

    def test_tipo_invalido_e_reportado(self):
        erros = validar({"classe": "nota_pessoal", "itens": [item(tipo="prova")]})
        self.assertTrue(any("tipo inválido" in e for e in erros), erros)

    def test_data_malformada_e_reportada(self):
        erros = validar({"classe": "nota_pessoal", "itens": [item(data="31/12/2026")]})
        self.assertTrue(any("AAAA-MM-DD" in e for e in erros), erros)

    def test_item_com_data_sem_curso_id_e_reportado(self):
        erros = validar({"classe": "nota_pessoal",
                         "itens": [item(data="2026-12-31", curso_id=None)]})
        self.assertTrue(any("curso_id" in e for e in erros), erros)

    def test_titulo_e_curso_obrigatorios(self):
        erros = validar({"classe": "nota_pessoal", "itens": [item(titulo=None, curso=None)]})
        self.assertTrue(any("titulo e curso" in e for e in erros), erros)


class PublicacaoLocalTests(unittest.TestCase):
    """Publicação real em ObjetosLocais via SURICATA_ESTADO_URI (in-process)."""

    def _publicar(self, dados: bytes, argv_extra: list[str] = ()) -> tuple[int, Path, str]:
        tmp = tempfile.mkdtemp()
        arquivo = Path(tmp) / "entrada.json"
        arquivo.write_bytes(dados)
        argv = ["publicar_agenda.py", "--arquivo", str(arquivo), *argv_extra]
        estado = Path(tmp) / "estado"
        from unittest import mock
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(os.environ, {"SURICATA_ESTADO_URI": str(estado)}):
            codigo = main()
        return codigo, estado, tmp

    def test_publicacao_cria_objeto_com_conteudo_exato(self):
        dados = agenda([item()])
        codigo, estado, _ = self._publicar(dados)
        self.assertEqual(codigo, 0)
        publicado = estado / OBJETO
        self.assertTrue(publicado.is_file(), "agenda/manual.json deveria existir")
        self.assertEqual(publicado.read_bytes(), dados)

    def test_dados_invalidos_sai_com_2_e_nao_escreve_nada(self):
        estado_raiz = tempfile.mkdtemp()
        arquivo = Path(estado_raiz) / "entrada.json"
        arquivo.write_bytes(agenda([item(tipo="prova")], classe="errada"))
        from unittest import mock
        argv = ["publicar_agenda.py", "--arquivo", str(arquivo)]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(os.environ, {"SURICATA_ESTADO_URI": str(estado_raiz)}):
            codigo = main()
        self.assertEqual(codigo, 2)
        restantes = [p for p in Path(estado_raiz).rglob("*") if p.name != "entrada.json"]
        self.assertEqual(restantes, [], f"escrita indevida: {restantes}")

    def test_sem_estado_uri_e_fail_closed(self):
        dados = agenda([item()])
        tmp = tempfile.mkdtemp()
        arquivo = Path(tmp) / "entrada.json"
        arquivo.write_bytes(dados)
        from unittest import mock
        env_sem = {k: v for k, v in os.environ.items() if k != "SURICATA_ESTADO_URI"}
        argv = ["publicar_agenda.py", "--arquivo", str(arquivo)]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(os.environ, env_sem, clear=True):
            codigo = main()
        self.assertEqual(codigo, 2)

    def test_validar_valida_sem_publicar(self):
        dados = agenda([item()])
        tmp = tempfile.mkdtemp()
        arquivo = Path(tmp) / "entrada.json"
        arquivo.write_bytes(dados)
        from unittest import mock
        argv = ["publicar_agenda.py", "--arquivo", str(arquivo), "--validar"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(os.environ, {"SURICATA_ESTADO_URI": str(Path(tmp) / "estado")}):
            codigo = main()
        self.assertEqual(codigo, 0)
        self.assertFalse((Path(tmp) / "estado").exists(), "--validar não deveria escrever")

    def test_dry_run_valida_sem_escrever(self):
        dados = agenda([item()])
        tmp = tempfile.mkdtemp()
        arquivo = Path(tmp) / "entrada.json"
        arquivo.write_bytes(dados)
        from unittest import mock
        argv = ["publicar_agenda.py", "--arquivo", str(arquivo), "--dry-run"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.dict(os.environ, {"SURICATA_ESTADO_URI": str(Path(tmp) / "estado")}):
            codigo = main()
        self.assertEqual(codigo, 0)
        self.assertFalse((Path(tmp) / "estado").exists(), "--dry-run não deveria escrever")


class SubprocessoTests(unittest.TestCase):
    """Subprocesso real; caminho --validar não precisa de rede."""

    def _rodar(self, dados: bytes, extra: list[str], env_extra: dict[str, str]) -> subprocess.CompletedProcess:
        tmp = tempfile.mkdtemp()
        arquivo = Path(tmp) / "entrada.json"
        arquivo.write_bytes(dados)
        env = dict(os.environ)
        env.update(env_extra)
        env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in [str(REPO), env.get("PYTHONPATH", "")] if p)
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--arquivo", str(arquivo), *extra],
            capture_output=True, text=True, env=env, cwd=str(REPO), timeout=60)

    def test_validar_subprocesso_exit_0(self):
        proc = self._rodar(agenda([item()]), ["--validar"], {})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_invalido_subprocesso_exit_nao_zero(self):
        proc = self._rodar(agenda([item()], classe="errada"), ["--validar"], {})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ERRO", proc.stdout + proc.stderr)

    def test_tripwire_sem_path_no_caminho_de_validacao(self):
        """PATH="" no trecho que só lê/valida: nenhum binário externo é exigido."""
        env = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "PATH": ""}
        proc = self._rodar(agenda([item()]), ["--validar"], env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_publicacao_subprocesso_objetos_locais(self):
        tmp = tempfile.mkdtemp()
        proc = self._rodar(agenda([item()]), [],
                           {"SURICATA_ESTADO_URI": str(Path(tmp) / "estado")})
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual((Path(tmp) / "estado" / OBJETO).read_bytes(), agenda([item()]))


if __name__ == "__main__":
    unittest.main()
