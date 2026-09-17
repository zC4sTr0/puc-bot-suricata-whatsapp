"""``python -m suricata --mode teste-envio``: medições M-WA-01 e M-WA-02 do plano.

Envia ao ``SURICATA_GRUPO_JID`` uma mensagem de teste e, numa **segunda
conexão**, a mesma mensagem com o **mesmo** ``message_id`` — exatamente o que um
reenvio sem ACK faria. O relatório traz ACK e status de cada envio; quantas
mensagens apareceram no grupo (1 ou 2) é a verificação humana H3.

Usa o mesmo lease da rodada: nunca abre a sessão ao mesmo tempo que ela.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from .bridge import WhatsAppBridge
from .message_id import message_id
from .rodada import Lease
from .storage.gcs import SessaoWhatsApp, construir_objetos

TEXTO = ("🦦 Suricata conectada pela nuvem.\n"
         "Teste de idempotência: esta mensagem foi enviada 2 vezes com o mesmo ID. "
         "Se aparecer só uma vez, o reenvio não duplica avisos.")


def main() -> int:
    uri, grupo = os.environ.get("SURICATA_ESTADO_URI", ""), os.environ.get("SURICATA_GRUPO_JID", "")
    if not uri or not grupo:
        print(json.dumps({"estado": "erro", "erro": "SURICATA_ESTADO_URI e SURICATA_GRUPO_JID são obrigatórios"}))
        return 5
    objetos = construir_objetos(uri)
    lease = Lease(objetos, lambda: datetime.now(timezone.utc))
    if not lease.adquirir():
        print(json.dumps({"estado": "lease_ocupado"}))
        return 4
    try:
        event_id = "grupo:teste:idempotencia:2026-09-14"
        evento = {"event_id": event_id, "message_id": message_id(grupo, event_id), "texto": TEXTO}
        ponte = WhatsAppBridge(SessaoWhatsApp(objetos))
        envios = []
        for tentativa in (1, 2):
            inicio = time.monotonic()
            resposta = ponte.enviar_lote(grupo, [dict(evento)])
            item = (resposta.get("resultados") or [{}])[0]
            envios.append({"tentativa": tentativa, "sessao": resposta.get("sessao"), "ack": item.get("ack"),
                           "status": item.get("status"), "segundos": round(time.monotonic() - inicio, 1)})
        print(json.dumps({"estado": "concluido", "message_id": evento["message_id"], "envios": envios}))
        return 0 if all(e["ack"] for e in envios) else 6
    finally:
        lease.liberar()


if __name__ == "__main__":
    raise SystemExit(main())
