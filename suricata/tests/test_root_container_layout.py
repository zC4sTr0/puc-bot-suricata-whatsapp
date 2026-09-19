import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def instructions(text):
    values = []
    pending = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            pending += line[:-1].rstrip() + " "
            continue
        values.append(pending + line)
        pending = ""
    return values


class RootContainerLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
        cls.ignore = (REPO / ".dockerignore").read_text(encoding="utf-8")
        cls.gcloudignore = (REPO / ".gcloudignore").read_text(encoding="utf-8")

    def test_ci_container_is_the_root_context_container(self):
        self.assertIn("COPY suricata /app/suricata", self.dockerfile)
        self.assertIn("COPY suricata/whatsapp/package.json suricata/whatsapp/package-lock.json /app/suricata/whatsapp/", self.dockerfile)
        self.assertIn("node:22-bookworm-slim@sha256:", self.dockerfile)
        self.assertIn('ENTRYPOINT ["python3", "-m", "suricata"]', self.dockerfile)
        self.assertIn('CMD ["--mode", "shadow"]', self.dockerfile)

    def test_root_context_excludes_runtime_secrets_and_state(self):
        for pattern in ("**/auth.json", "**/.wa-auth*/", "**/session/", "**/*.db", "**/*.pem", ".env"):
            self.assertIn(pattern, self.ignore)
        for pattern in ("**/auth.json", "**/.wa-auth*/", "**/session/", "**/*.db", ".env"):
            self.assertIn(pattern, self.gcloudignore)

    def test_root_entrypoint_is_shadow_by_default(self):
        commands = [line.split(" ", 1)[1] for line in instructions(self.dockerfile) if line.startswith("CMD ")]
        self.assertEqual([json.loads(value) for value in commands], [["--mode", "shadow"]])


if __name__ == "__main__":
    unittest.main()
