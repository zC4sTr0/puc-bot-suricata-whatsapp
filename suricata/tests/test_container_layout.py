import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _docker_instructions(text):
    """Return real Dockerfile instructions, excluding comment lines."""
    logical_lines = []
    pending = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not pending and line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].rstrip() + " "
            continue
        logical_lines.append(pending + line)
        pending = ""
    if pending:
        logical_lines.append(pending.rstrip())

    instructions = []
    for line in logical_lines:
        name, separator, argument = line.partition(" ")
        if separator:
            instructions.append((name.upper(), argument.strip()))
        else:
            instructions.append((name.upper(), ""))
    return instructions


def _instruction_values(text, name):
    return [argument for instruction, argument in _docker_instructions(text) if instruction == name]


class ContainerLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        cls.ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
        cls.gcloudignore = (ROOT / ".gcloudignore").read_text(encoding="utf-8")

    def test_empacotamento_proprio_existe_e_instala_lockfile_do_whatsapp(self):
        instructions = _docker_instructions(self.dockerfile)
        from_instructions = _instruction_values(self.dockerfile, "FROM")
        self.assertEqual(len(from_instructions), 1)
        # Base sempre digest-pinned (reprodutibilidade do build).
        self.assertTrue(
            from_instructions[0].startswith("node:22-bookworm-slim@sha256:"),
            f"FROM não é digest-pinned: {from_instructions[0]!r}",
        )
        self.assertIn(
            ("COPY", "whatsapp/package.json whatsapp/package-lock.json ./suricata/whatsapp/"),
            instructions,
        )
        self.assertIn(
            (
                "RUN",
                "npm ci --omit=dev --prefix ./suricata/whatsapp && npm cache clean --force",
            ),
            instructions,
        )
        install = " ".join(_instruction_values(self.dockerfile, "RUN"))
        for tool in ("git", "openssh-client", "ca-certificates"):
            self.assertIn(tool, install)
        self.assertIn(("USER", "suricata"), instructions)

    def test_contexto_exclui_sessao_e_dependencias_geradas(self):
        for forbidden in (".wa-auth*/", "whatsapp/node_modules/", ".env", "grupos.json"):
            self.assertIn(forbidden, self.ignore)

    def test_contexto_docker_exclui_bancos_e_variantes_do_upload_gcloud(self):
        docker_patterns = {
            line.strip()
            for line in self.ignore.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        gcloud_db_patterns = {
            line.strip()
            for line in self.gcloudignore.splitlines()
            if ".db" in line and line.strip() and not line.lstrip().startswith("#")
        }

        self.assertEqual(gcloud_db_patterns, {"*.db", "*.db-*"})
        self.assertTrue(gcloud_db_patterns <= docker_patterns)
        self.assertIn("**/*.db", docker_patterns)
        self.assertIn("**/*.db-*", docker_patterns)

    def test_contexto_docker_mantem_fronteiras_de_segredos(self):
        for forbidden in (
            "auth.json",
            ".wa-auth*/",
            "**/session/",
            "**/sessions/",
            "*.log",
            "*.pem",
            "*.key",
            "*.qr",
            "*qr*.png",
        ):
            self.assertIn(forbidden, self.ignore)

    def test_upload_gcloud_exclui_auth_e_sessao(self):
        for forbidden in ("auth.json", ".wa-auth*/", "**/auth/", "**/session/", ".env"):
            self.assertIn(forbidden, self.gcloudignore)

    def test_comentario_nao_e_instrução_docker(self):
        dockerfile = '# CMD ["--version"]\nCMD ["--mode", "sentinela"]\n'

        self.assertEqual(_instruction_values(dockerfile, "CMD"), ['["--mode", "sentinela"]'])

    def test_instrucoes_de_execucao_reais_sao_as_atuais(self):
        entrypoints = _instruction_values(self.dockerfile, "ENTRYPOINT")
        commands = _instruction_values(self.dockerfile, "CMD")

        self.assertEqual([json.loads(value) for value in entrypoints], [["python3", "-m", "suricata"]])
        self.assertEqual([json.loads(value) for value in commands], [["--mode", "shadow"]])

    def test_cmd_padrao_nao_inicia_sentinela_sem_config(self):
        command = json.loads(_instruction_values(self.dockerfile, "CMD")[0])
        self.assertEqual(command, ["--mode", "shadow"])
        self.assertNotIn("--config", command)
        self.assertNotIn("sentinela", command)

    def test_caminhos_de_copy_sao_relativos_ao_contexto_suricata(self):
        copies = [shlex.split(value) for value in _instruction_values(self.dockerfile, "COPY")]

        self.assertIn(
            ["whatsapp/package.json", "whatsapp/package-lock.json", "./suricata/whatsapp/"],
            copies,
        )
        self.assertIn([".", "./suricata/"], copies)
        self.assertTrue(all(not source.startswith("suricata/") for copy in copies for source in copy[:-1]))

    def test_entrypoint_configurado_executa_como_pacote_a_partir_de_app(self):
        entrypoint = json.loads(_instruction_values(self.dockerfile, "ENTRYPOINT")[0])
        command = json.loads(_instruction_values(self.dockerfile, "CMD")[0])
        self.assertEqual(entrypoint, ["python3", "-m", "suricata"])

        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / "app"
            package = app / "suricata"
            package.mkdir(parents=True)
            for source in ROOT.glob("*.py"):
                shutil.copy2(source, package / source.name)
            for source_dir in ("storage",):
                shutil.copytree(ROOT / source_dir, package / source_dir)

            result = subprocess.run(
                [sys.executable, *entrypoint[1:], *command],
                cwd=app,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"mode": "shadow", "status": "ok", "adapter": "none"},
        )
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
