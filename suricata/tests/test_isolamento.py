import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "infra" / "isolamento.json"
FORBIDDEN = (
    "scripts.academico",
    "academico.",
    "puc-bot-20260912",
    "gs://puc-bot-20260912-estado",
    "telegram-token",
    "telegram-webhook-secret",
)


class IsolamentoTests(unittest.TestCase):
    def test_manifesto_tem_projeto_e_prefixo_proprios(self):
        manifesto = json.loads(MANIFEST.read_text(encoding="utf-8"))
        gcp = manifesto["gcp"]
        self.assertEqual(gcp["project_id"], "example-suricata-project")
        self.assertEqual(gcp["resource_prefix"], "suricata-")
        self.assertEqual(manifesto["repository"]["root"], "suricata/")

    def test_implementacao_suricata_nao_importa_nem_aponta_para_telegram(self):
        arquivos = [
            *ROOT.rglob("*.py"),
            *ROOT.rglob("*.mjs"),
            *ROOT.rglob("*.json"),
        ]
        arquivos = [p for p in arquivos if p != MANIFEST and "tests" not in p.parts]
        for caminho in arquivos:
            conteudo = caminho.read_text(encoding="utf-8")
            for proibido in FORBIDDEN:
                self.assertNotIn(proibido, conteudo, f"referência proibida em {caminho}")


if __name__ == "__main__":
    unittest.main()
