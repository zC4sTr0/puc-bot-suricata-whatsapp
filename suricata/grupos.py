"""``python -m suricata --mode grupos``: descobre o JID do grupo usando a sessão do bucket.

Materializa a sessão num diretório temporário, roda ``whatsapp/grupos.mjs`` e
devolve a sessão ao bucket por CAS se o Baileys a tiver atualizado. Imprime só
nome, JID e contagem de participantes — nenhum telefone nem conteúdo de sessão.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .bridge import WhatsAppBridge
from .storage.gcs import SessaoWhatsApp, construir_objetos


def main() -> int:
    uri = os.environ.get("SURICATA_ESTADO_URI", "")
    if not uri:
        print(json.dumps({"sessao": "erro", "erro": "SURICATA_ESTADO_URI ausente (use um diretório local ou gs://...)"}))
        return 5
    sessao = SessaoWhatsApp(construir_objetos(uri))
    snapshot = sessao.read_auth()
    if snapshot.value is None:
        print(json.dumps({"sessao": "ausente", "grupos": []}))
        return 6
    script = Path(__file__).with_name("whatsapp") / "grupos.mjs"
    with tempfile.TemporaryDirectory(prefix=".wa-auth-") as temp:
        auth_dir = Path(temp) / "auth"
        WhatsAppBridge._materializar(snapshot.value, auth_dir)
        concluido = subprocess.run(["node", str(script), "--auth-dir", str(auth_dir)], capture_output=True,
                                   timeout=120, check=False, env={"PATH": os.environ.get("PATH", "")})
        try:
            resultado = json.loads(concluido.stdout.decode("utf-8").strip().splitlines()[-1])
        except (IndexError, UnicodeDecodeError, ValueError):
            resultado = {"sessao": "erro", "grupos": [], "erro": "saída inválida do grupos.mjs"}
        atualizado = WhatsAppBridge._ler_auth(auth_dir)
        if resultado.get("sessao") == "ok" and atualizado != snapshot.value:
            sessao.write_auth(atualizado, expected_generation=snapshot.generation)
    print(json.dumps(resultado, ensure_ascii=False))
    return 0 if resultado.get("sessao") == "ok" else 6


if __name__ == "__main__":
    raise SystemExit(main())
