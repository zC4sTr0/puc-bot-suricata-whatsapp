"""Notificador público do grupo WhatsApp, com entrega durável via Outbox."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
from collections import Counter
import re
import unicodedata

from ..bridge import BridgeError, WhatsAppBridge
from ..domain import DomainError, EventoPublico, normalizar_evento, renderizar_publico
from ..message_id import message_id
from ..outbox import Outbox, OutboxError
from ..storage.cas import CASConflict


MAX_ERRO = 200


def _erro_seguro(value: Any, padrao: str = "falha na entrega WhatsApp") -> str:
    """Converte falhas externas em texto curto, sem payload ou segredo."""
    if isinstance(value, CASConflict):
        value = "sessão WhatsApp alterada por outro processo"
    elif isinstance(value, BridgeError):
        value = str(value)
    elif not isinstance(value, str):
        value = padrao
    return value[:MAX_ERRO]


class WhatsAppGrupo:
    nome = "whatsapp"

    def __init__(
        self,
        armazenamento: Any,
        grupo_jid: str,
        *,
        node: str = "node",
        script: str | Path | None = None,
        bridge: WhatsAppBridge | None = None,
    ) -> None:
        if not isinstance(grupo_jid, str) or not grupo_jid:
            raise ValueError("grupo_jid obrigatório")
        self.grupo_jid = grupo_jid
        self.bridge = bridge or WhatsAppBridge(
            armazenamento, node=node, script=script
        )

    def __repr__(self) -> str:
        return f"WhatsAppGrupo(nome={self.nome!r}, grupo_jid={self.grupo_jid!r})"

    def enviar_lote(self, eventos: list[dict[str, Any] | EventoPublico]) -> list[dict[str, Any]]:
        """Envia um lote e devolve somente resultados sanitizados do bridge."""
        if not isinstance(eventos, list) or not eventos:
            raise ValueError("eventos deve ser uma lista não vazia")
        preparados = [_preparar_evento(evento, self.grupo_jid) for evento in eventos]
        try:
            resposta = self.bridge.enviar_lote(self.grupo_jid, preparados)
        except CASConflict as exc:
            return [
                _resultado(evento, "erro", erro=_erro_seguro(exc))
                for evento in preparados
            ]
        except BridgeError as exc:
            return [
                _resultado(evento, "erro", erro=_erro_seguro(exc))
                for evento in preparados
            ]
        except Exception:
            # Não propaga detalhes de subprocesso, sessão ou armazenamento.
            return [
                _resultado(evento, "erro", erro="falha na entrega WhatsApp")
                for evento in preparados
            ]

        sessao = resposta.get("sessao", "erro") if isinstance(resposta, dict) else "erro"
        brutos = resposta.get("resultados") if isinstance(resposta, dict) else None
        if not isinstance(brutos, list):
            return [_resultado(evento, sessao, erro="resultados ausentes ou inválidos") for evento in preparados]
        ids_esperados = Counter(evento["event_id"] for evento in preparados)
        ids_recebidos = Counter(item.get("event_id") for item in brutos if isinstance(item, dict))
        if len(brutos) != len(preparados) or ids_recebidos != ids_esperados:
            if len(brutos) > len(preparados) or any(
                count > ids_esperados[event_id] for event_id, count in ids_recebidos.items()
            ):
                erro = "resultado duplicado ou extra"
            else:
                erro = "resultado ausente"
            return [_resultado(evento, sessao, erro=erro) for evento in preparados]
        por_evento = {item["event_id"]: item for item in brutos}
        saida = []
        for evento in preparados:
            item = por_evento[evento["event_id"]]
            message_ok = item.get("message_id") == evento["message_id"]
            ack = sessao == "ok" and message_ok and item.get("ack") is True
            erro = _erro_seguro(item.get("erro")) if item.get("erro") else None
            if not message_ok:
                erro = "message_id divergente"
            saida.append(_resultado(evento, sessao, ack=ack,
                                    status=item.get("status") if type(item.get("status")) is int else None,
                                    erro=erro))
        return saida


def entregar_grupo(
    outbox: Outbox,
    notificador: WhatsAppGrupo,
    eventos: Iterable[dict[str, Any] | EventoPublico],
    momento: Any = None,
) -> list[dict[str, Any]]:
    """Registra, reivindica, entrega uma vez e confirma ACK no outbox."""
    agora = momento
    registrados = []
    for evento in eventos:
        if not isinstance(evento, (dict, EventoPublico)):
            raise ValueError("evento público inválido")
        preparados = _preparar_evento(evento, notificador.grupo_jid)
        registrados.append(outbox.adicionar(preparados, agora=agora))

    outbox.expirar(agora=agora)
    claims = []
    for record in registrados:
        try:
            claims.append(outbox.reivindicar(record["event_id"], agora=agora))
        except OutboxError:
            continue

    if not claims:
        return [dict(r) for r in registrados]

    try:
        resultados = notificador.enviar_lote(claims)
    except Exception:
        resultados = [{"event_id": c["event_id"], "sessao": "erro", "erro": "falha na entrega WhatsApp"} for c in claims]

    por_evento, erros = _indexar_resultados(resultados, claims)
    registros = {record["event_id"]: dict(record) for record in registrados}
    for claim in claims:
        result = por_evento.get(claim["event_id"], {})
        ack = (not erros.get(claim["event_id"])) and result.get("sessao") == "ok" \
            and result.get("message_id") == claim["message_id"] \
            and result.get("ack") is True and type(result.get("status")) is int and result["status"] >= 2
        if ack:
            try:
                registros[claim["event_id"]] = outbox.aplicar_resultado(
                    claim["event_id"], attempt_id=claim["attempt_id"],
                    message_id=claim["message_id"], ack=True, status=result["status"]
                )
            except OutboxError:
                registros[claim["event_id"]] = _devolver_pending(outbox, claim["event_id"])
        else:
            registros[claim["event_id"]] = _devolver_pending(outbox, claim["event_id"])
        if result.get("erro"):
            erros.setdefault(claim["event_id"], _erro_seguro(result["erro"]))
    return [{**registros[r["event_id"]], **({"erro": erros[r["event_id"]]} if r["event_id"] in erros else {})}
            for r in registrados]


_TERMOS_PRIVADOS = re.compile(
    r"(?i)(?<!\\w)(?:submission|submissions|entrega|entregas|entregue|"
    r"entregues|entregado|entregada|atraso|atrasos|nota|notas|"
    r"situacao|situacoes|perdido|perdida|perdidos|perdidas)(?!\\w)"
)


def _sem_acento(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", value.casefold())
        if unicodedata.category(char) != "Mn"
    )


def _validar_payload_cru(value: Any) -> None:
    """Impede que payloads legados contornem a projeção pública."""
    if isinstance(value, dict):
        for key, child in value.items():
            if _TERMOS_PRIVADOS.search(_sem_acento(str(key))):
                raise ValueError("payload WhatsApp contém campo privado")
            _validar_payload_cru(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validar_payload_cru(child)
    elif isinstance(value, str) and _TERMOS_PRIVADOS.search(_sem_acento(value)):
        raise ValueError("payload WhatsApp contém conteúdo privado")


def _preparar_evento(evento: dict[str, Any] | EventoPublico, grupo_jid: str) -> dict[str, Any]:
    if isinstance(evento, EventoPublico):
        publico = evento
    elif isinstance(evento, dict):
        _validar_payload_cru(evento)
        try:
            publico = normalizar_evento(evento)
        except DomainError:
            # Compatibilidade com o contrato legado de texto já renderizado:
            # ele também passa por uma projeção pública antes do transporte.
            if not isinstance(evento.get("texto"), str) or not evento["texto"]:
                raise ValueError("evento público inválido")
            publico = normalizar_evento({
                "event_id": evento.get("event_id"),
                "curso": "",
                "titulo": evento["texto"],
                "tipo": "tarefa",
            })
    else:
        raise ValueError("evento público inválido")

    texto = renderizar_publico(publico)
    esperado = message_id(grupo_jid, publico.event_id)
    if isinstance(evento, dict) and evento.get("message_id", esperado) != esperado:
        raise ValueError("message_id não determinístico")
    return {"event_id": publico.event_id, "message_id": esperado, "texto": texto}


def _resultado(evento: dict[str, Any], sessao: str, *, ack: bool = False, status: int | None = None, erro: str | None = None) -> dict[str, Any]:
    return {"event_id": evento["event_id"], "message_id": evento["message_id"], "sessao": sessao, "ack": ack, "status": status, "erro": erro}


def _devolver_pending(outbox: Outbox, event_id: str) -> dict[str, Any]:
    return outbox.transicionar(event_id, "pending")


def _indexar_resultados(resultados: Any, claims: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    esperados = Counter(claim["event_id"] for claim in claims)
    if not isinstance(resultados, list):
        return {}, {claim["event_id"]: "resultados ausentes ou inválidos" for claim in claims}
    recebidos = Counter(item.get("event_id") for item in resultados if isinstance(item, dict))
    if len(resultados) != len(claims) or recebidos != esperados:
        erro = "resultado duplicado ou extra" if any(
            count > esperados[event_id] for event_id, count in recebidos.items()
        ) else "resultado ausente"
        return {}, {claim["event_id"]: erro for claim in claims}
    return {item["event_id"]: item for item in resultados}, {}


__all__ = ["WhatsAppGrupo", "entregar_grupo"]
