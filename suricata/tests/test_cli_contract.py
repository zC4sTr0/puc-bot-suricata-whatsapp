"""Contrato CLI congelado por subprocesso real: exit code + stdout JSON (1.2).

Caracterização do comportamento atual: cada teste executa
``python -m suricata`` em subprocesso real (``sys.executable``, cwd na raiz do
repo, ambiente controlado sem nenhuma variável ``SURICATA_*``) e fixa o código
de saída e o JSON exato impresso em stdout (parse + asserção chave a chave).

Exit 3 (``Canvas indisponível``) não é comparável offline: o allowlist de
origem em ``suricata/canvas.py`` só aceita ``https://pucminas.instructure.com``
(hostname idêntico ao ``ORIGIN``, HTTPS, porta 443/None). Um servidor local em
127.0.0.1 nunca passa pela validação — origens não allowlisted resultam em
exit 2 (``configuração inválida``) antes de qualquer rede — e exercitar o
caminho de rede exigiria a origem externa real, proibida pelas regras do repo.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # raiz do repo (contém o pacote suricata/)


def _ambiente_controlado() -> dict[str, str]:
    """Cópia do ambiente sem nenhuma variável SURICATA_* herdada."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("SURICATA_")
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _executar_cli(*argumentos: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "suricata", *argumentos],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=_ambiente_controlado(),
        timeout=120,
    )


class ContratoCLITests(unittest.TestCase):
    def _linha_unica(self, result: subprocess.CompletedProcess) -> str:
        linhas = result.stdout.splitlines()
        self.assertEqual(len(linhas), 1, f"stdout: {result.stdout!r} stderr: {result.stderr!r}")
        return linhas[0]

    def _payload(self, result: subprocess.CompletedProcess) -> dict:
        return json.loads(self._linha_unica(result))

    def test_shadow_ok_exit_0(self):
        result = _executar_cli("--mode", "shadow")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        # Serialização compacta do _emit: separadores (",", ":") sem espaços.
        self.assertEqual(
            self._linha_unica(result),
            '{"mode":"shadow","status":"ok","adapter":"none"}',
        )
        payload = self._payload(result)
        self.assertEqual(set(payload), {"mode", "status", "adapter"})
        self.assertEqual(payload["mode"], "shadow")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["adapter"], "none")

    def test_modo_ausente_exit_2(self):
        result = _executar_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            self._linha_unica(result),
            '{"status":"error","error":"modo ausente"}',
        )
        payload = self._payload(result)
        self.assertEqual(set(payload), {"status", "error"})
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "modo ausente")

    def test_modo_invalido_exit_2(self):
        result = _executar_cli("--mode", "foo")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            self._linha_unica(result),
            '{"status":"error","error":"modo inválido"}',
        )
        payload = self._payload(result)
        self.assertEqual(set(payload), {"status", "error"})
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "modo inválido")

    def test_argumentos_invalidos_exit_2(self):
        # Flag desconhecida ou valor ausente é rejeitada antes do dispatch.
        for argumentos in (("--flag", "x"), ("--mode",)):
            with self.subTest(argumentos=argumentos):
                result = _executar_cli(*argumentos)
                self.assertEqual(result.returncode, 2, result.stderr)
                payload = self._payload(result)
                self.assertEqual(set(payload), {"status", "error"})
                self.assertEqual(payload["status"], "error")
                self.assertEqual(payload["error"], "argumentos inválidos")

    def test_sentinela_sem_config_exit_2(self):
        result = _executar_cli("--mode", "sentinela")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            self._linha_unica(result),
            '{"mode":"sentinela","status":"error","error":"configuração ausente"}',
        )
        payload = self._payload(result)
        self.assertEqual(set(payload), {"mode", "status", "error"})
        self.assertEqual(payload["mode"], "sentinela")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "configuração ausente")

    def test_sentinela_config_inexistente_exit_2(self):
        with tempfile.TemporaryDirectory() as directory:
            caminho = Path(directory) / "nao-existe.json"
            result = _executar_cli("--mode", "sentinela", "--config", str(caminho))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr, "")
        payload = self._payload(result)
        self.assertEqual(set(payload), {"mode", "status", "error"})
        self.assertEqual(payload["mode"], "sentinela")
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"], "configuração inválida")

    def test_rodada_sem_env_exit_5(self):
        # Sem SURICATA_ESTADO_URI a rodada falha em código 5 (armazenamento)
        # com payload {"estado": "erro", "erro": ...} — caminho runtime.py,
        # não _emit: json.dumps com separadores padrão (com espaços).
        result = _executar_cli("--mode", "rodada")
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            self._linha_unica(result),
            '{"estado": "erro", "erro": "SURICATA_ESTADO_URI ausente"}',
        )
        payload = self._payload(result)
        self.assertEqual(set(payload), {"estado", "erro"})
        self.assertEqual(payload["estado"], "erro")
        self.assertEqual(payload["erro"], "SURICATA_ESTADO_URI ausente")


if __name__ == "__main__":
    unittest.main()
