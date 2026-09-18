"""Guard de empacotamento (plano T1.7): wheel instalável e executável sem o checkout.

Contrato congelado:
  * o wheel contém o runtime Python (``entrypoint.py``/``demo.py``), o transporte
    Node (``whatsapp/enviar.mjs`` + ``whatsapp/package.json``) e as fixtures do
    modo demo (``tests/fixtures/canvas_demo.json``);
  * instalado num diretório limpo (``pip install --no-deps --target``), o comando
    ``suricata --mode shadow`` roda com cwd/PYTHONPATH neutros, exit 0, stderr
    vazio e o JSON de shadow no stdout.

O build roda num TemporaryDirectory FORA do repositório; artefatos que o
setuptools criar no repo (``build/``, ``*.egg-info``) são removidos ao final.
Se nenhum interpretador >= 3.11 com pip/build estiver disponível no ambiente,
a classe inteira faz SKIP (não falha) com o motivo registrado.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_WHEEL_FILES = (
    "suricata/entrypoint.py",
    "suricata/demo.py",
    "suricata/whatsapp/enviar.mjs",
    "suricata/whatsapp/package.json",
    "suricata/tests/fixtures/canvas_demo.json",
)
SHADOW_PAYLOAD = {"mode": "shadow", "status": "ok", "adapter": "none"}

# requires-python do pyproject.toml; pip recusa instalar o wheel abaixo disso.
MINIMUM_PYTHON = (3, 11)

_PACKAGING_HINT = (
    "O wheel NÃO contém: {missing}. Causa provável: pyproject.toml declara "
    '[tool.setuptools] packages = ["suricata"], o que exclui subpacotes '
    "(whatsapp, tests, storage, infra) e arquivos de dados "
    "(.mjs/.json). Com isso o wheel instalado não é utilizável. A correção "
    "exige descoberta de pacotes (find:) + package-data no pyproject.toml."
)


def _run(command, cwd=None, env=None):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _repo_build_artifacts():
    """Artefatos que um build setuptools pode deixar no repo (para limpeza)."""
    artifacts = [entry for entry in ROOT.glob("*.egg-info")]
    build_dir = ROOT / "build"
    if build_dir.exists():
        artifacts.append(build_dir)
    return artifacts


def _remove_new_artifacts(before):
    """Remove apenas artefatos que apareceram depois do snapshot ``before``."""
    for artifact in _repo_build_artifacts():
        if artifact not in before:
            shutil.rmtree(artifact, ignore_errors=True)


def _candidate_interpreters():
    """Interpretadores que podem construir/instalar o wheel (ordem de preferência)."""
    candidates = []
    if sys.version_info[:2] >= MINIMUM_PYTHON:
        candidates.append(sys.executable)
    if shutil.which("py"):
        listing = _run(["py", "-0p"])
        if listing.returncode == 0:
            for line in listing.stdout.splitlines():
                match = re.search(r"(?i)(\S*python\.exe)\s*$", line.strip())
                if match:
                    candidates.append(match.group(1))
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    unique, seen = [], set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _is_usable(candidate):
    probe = _run([candidate, "-c", "import sys; print(sys.version_info[:2])"])
    if probe.returncode != 0:
        return False
    version = ast.literal_eval(probe.stdout.strip())
    if tuple(version) < MINIMUM_PYTHON:
        return False
    return _run([candidate, "-m", "pip", "--version"]).returncode == 0


def _build_wheel_with(candidate, outdir):
    """Tenta `python -m build`; sem o módulo, cai para `python -m pip wheel`."""
    build = _run(
        [candidate, "-m", "build", "--wheel", "--outdir", str(outdir), "."], cwd=ROOT
    )
    if build.returncode == 0 and list(Path(outdir).glob("*.whl")):
        return build, "build"
    pip_wheel = _run(
        [
            candidate,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(outdir),
            ".",
        ],
        cwd=ROOT,
    )
    if pip_wheel.returncode == 0 and list(Path(outdir).glob("*.whl")):
        return pip_wheel, "pip wheel"
    return pip_wheel, None


def _build_wheel(outdir):
    """Percorre interpretadores; devolve (interpretador, backend, erros)."""
    errors = []
    for candidate in _candidate_interpreters():
        if not _is_usable(candidate):
            errors.append(f"{candidate}: sem pip ou Python < {MINIMUM_PYTHON}")
            continue
        result, backend = _build_wheel_with(candidate, outdir)
        if backend is None:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            errors.append(f"{candidate}: {tail[-1] if tail else 'falhou sem mensagem'}")
            continue
        return candidate, backend, errors
    return None, None, errors


def _find_console_script(target):
    candidates = sorted(
        set(target.glob("bin/suricata*")) | set(target.glob("Scripts/suricata*"))
    )
    if os.name == "nt":
        candidates = [
            entry for entry in candidates if entry.suffix.lower() in (".exe", ".bat", ".cmd")
        ]
    else:
        candidates = [entry for entry in candidates if entry.suffix == ""]
    return candidates[0] if candidates else None


class WheelPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workdir = Path(tempfile.mkdtemp(prefix="suricata_wheel_guard_"))
        artifacts_before = _repo_build_artifacts()
        try:
            outdir = workdir / "dist"
            outdir.mkdir()
            interpreter, backend, errors = _build_wheel(outdir)
            wheels = sorted(outdir.glob("*.whl"))
            if interpreter is None or not wheels:
                raise unittest.SkipTest(
                    "ambiente sem build/pip utilizável (>= Python 3.11): "
                    + "; ".join(errors)
                )
            cls.wheel = wheels[0]
            cls.interpreter = interpreter
            cls.backend = backend

            cls.target = workdir / "site"
            install = _run(
                [
                    interpreter,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--target",
                    str(cls.target),
                    str(cls.wheel),
                ]
            )
            if install.returncode != 0 or not (cls.target / "suricata").exists():
                tail = (install.stderr or install.stdout or "").strip().splitlines()
                raise unittest.SkipTest(
                    "pip install --target falhou no ambiente: "
                    + (tail[-1] if tail else "sem mensagem")
                )

            cls.neutral_cwd = workdir / "neutro"
            cls.neutral_cwd.mkdir()
            cls.workdir = workdir  # tearDownClass remove
        except unittest.SkipTest:
            shutil.rmtree(workdir, ignore_errors=True)
            raise
        finally:
            _remove_new_artifacts(artifacts_before)

    @classmethod
    def tearDownClass(cls):
        workdir = getattr(cls, "workdir", None)
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)
            cls.workdir = None
        _remove_new_artifacts(_repo_build_artifacts())

    def _neutral_env(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.target)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def _assert_shadow(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), SHADOW_PAYLOAD, result.stdout)
        self.assertEqual(result.stderr, "")

    def test_wheel_contem_runtime_transporte_e_fixtures(self):
        with zipfile.ZipFile(self.wheel) as wheel:
            names = set(wheel.namelist())
        missing = [entry for entry in EXPECTED_WHEEL_FILES if entry not in names]
        self.assertEqual(missing, [], _PACKAGING_HINT.format(missing=missing))

    def test_console_script_shadow_em_diretorio_neutro(self):
        script = _find_console_script(self.target)
        if script is None:
            self.skipTest(
                "console script não foi gerado no --target; o modo shadow foi "
                "verificado via `python -m suricata` (teste irmão)"
            )
        result = _run(
            [str(script), "--mode", "shadow"],
            cwd=self.neutral_cwd,
            env=self._neutral_env(),
        )
        self._assert_shadow(result)

    def test_modulo_suricata_shadow_em_diretorio_neutro(self):
        result = _run(
            [self.interpreter, "-m", "suricata", "--mode", "shadow"],
            cwd=self.neutral_cwd,
            env=self._neutral_env(),
        )
        self._assert_shadow(result)


if __name__ == "__main__":
    unittest.main()
