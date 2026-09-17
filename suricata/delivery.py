"""Orquestração local, durável e fail-closed da entrega pública.

A classe deste módulo coordena somente o outbox e uma ponte injetada. Não
inicia Node, não usa rede e nunca considera um ACK válido sem a identidade
completa da tentativa (event_id + message_id + attempt_id) e confirmação de
servidor.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from .domain import DomainError, EventoPublico, normalizar_evento, renderizar_publico
from .message_id import message_id
from .outbox import Outbox, OutboxError


class DeliveryError(ValueError):
    """Evento não pertence ao contrato público de delivery."""


_ALLOWED_FIELDS = frozenset({
    "event_id", "id", "curso", "titulo", "tipo", "eh_quiz", "unlock_at",
    "due_at", "lock_at", "pontos", "url", "expira_em",
})


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, datetime):
        raise TypeError("clock deve retornar datetime")
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class DeliveryOrchestrator:
    """Registra, reivindica, entrega e confirma eventos públicos.

    ``bridge_runner`` pode ser uma função ``(grupo_jid, eventos) -> dict`` ou
    um objeto com ``enviar_lote`` (por exemplo, ``WhatsAppGrupo``). O runner
    recebe apenas a projeção pública persistida no outbox. O retorno do runner
    aceita tanto o envelope do bridge quanto a lista sanitizada devolvida por
    ``WhatsAppGrupo.enviar_lote``.
    """

    def __init__(
        self,
        outbox: Outbox,
        grupo_jid: str,
        bridge_runner: Callable[[str, list[dict[str, Any]]], Any] | Any,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(grupo_jid, str) or not grupo_jid:
            raise ValueError("grupo_jid obrigatório")
        if not callable(bridge_runner) and not callable(getattr(bridge_runner, "enviar_lote", None)):
            raise TypeError("bridge_runner deve ser chamável")
        self.outbox = outbox
        self.grupo_jid = grupo_jid
        self.bridge_runner = bridge_runner
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def deliver(self, events: Iterable[Mapping[str, Any] | EventoPublico]) -> list[dict[str, Any]]:
        """Entrega um lote; falhas de transporte deixam os eventos pendentes."""
        try:
            raw_events = list(events)
        except TypeError as exc:
            raise DeliveryError("eventos públicos inválidos") from exc
        if not raw_events:
            return []
        now = _utc(self.clock())
        registered: list[dict[str, Any]] = []
        for raw in raw_events:
            prepared = self._prepare(raw, now)
            try:
                registered.append(self.outbox.adicionar(prepared, agora=now))
            except OutboxError as exc:
                raise DeliveryError("não foi possível registrar evento público") from exc

        expired = {item["event_id"]: item for item in self.outbox.expirar(agora=now)}
        claims: list[dict[str, Any]] = []
        results: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for record in registered:
            event_id = record["event_id"]
            if event_id in expired:
                results[event_id] = expired[event_id]
                continue
            if record.get("estado") == "sent":
                results[event_id] = record
                continue
            try:
                claims.append(self.outbox.reivindicar(event_id, agora=now))
            except OutboxError:
                # A duplicate in the same batch, or a concurrent worker, is
                # not permission to send again. Refresh the durable snapshot
                # and report its actual state instead of sending again.
                self.outbox.pendentes()  # also refreshes the instance snapshot
                current = getattr(self.outbox, "_eventos", {}).get(event_id)
                if isinstance(current, dict):
                    results[event_id] = dict(current)
                    if current.get("estado") != "sent":
                        errors.setdefault(event_id, "evento não reivindicado")
                else:
                    errors.setdefault(event_id, "evento não reivindicado")

        if claims:
            response = self._run(claims)
            normalized = self._normalize_response(response, claims)
            indexed = self._index_response(normalized, claims)
            for claim in claims:
                event_id = claim["event_id"]
                item = indexed.get(event_id)
                valid_ack = self._valid_ack(claim, normalized, item)
                try:
                    results[event_id] = self.outbox.aplicar_resultado(
                        event_id,
                        attempt_id=claim["attempt_id"],
                        message_id=claim["message_id"],
                        ack=valid_ack,
                        status=item.get("status") if isinstance(item, dict) and type(item.get("status")) is int else None,
                    )
                except OutboxError:
                    # Do not turn an uncertain/late result into sent.
                    results[event_id] = self._pending(claim)
                if not valid_ack:
                    errors.setdefault(event_id, "ACK ausente, divergente ou inválido")

        output = []
        for record in registered:
            event_id = record["event_id"]
            item = results.get(event_id)
            if item is None:
                item = self._pending(record)
            output.append({**item, **({"erro": errors[event_id]} if event_id in errors else {})})
        return output

    def deliver_event(self, event: Mapping[str, Any] | EventoPublico) -> dict[str, Any]:
        return self.deliver([event])[0]

    def _prepare(self, raw: Mapping[str, Any] | EventoPublico, now: datetime) -> dict[str, Any]:
        if isinstance(raw, EventoPublico):
            public = raw
            expiry = None
        elif isinstance(raw, Mapping):
            unknown = set(raw) - _ALLOWED_FIELDS
            if unknown:
                raise DeliveryError("evento contém campo fora da allowlist pública")
            try:
                public = normalizar_evento(raw)
            except DomainError as exc:
                raise DeliveryError("evento público inválido") from exc
            expiry = raw.get("expira_em")
            if expiry is not None and (not isinstance(expiry, str) or not expiry):
                raise DeliveryError("expira_em inválido")
        else:
            raise DeliveryError("evento público inválido")
        event_id = public.event_id
        prepared: dict[str, Any] = {
            "event_id": event_id,
            "message_id": message_id(self.grupo_jid, event_id),
            "texto": renderizar_publico(public, now),
        }
        if expiry is not None:
            prepared["expira_em"] = expiry
        return prepared

    def _run(self, claims: list[dict[str, Any]]) -> Any:
        try:
            if callable(self.bridge_runner):
                return self.bridge_runner(self.grupo_jid, claims)
            return self.bridge_runner.enviar_lote(self.grupo_jid, claims)
        except Exception:
            return None

    @staticmethod
    def _normalize_response(response: Any, claims: list[dict[str, Any]]) -> Any:
        """Converte o retorno sanitizado do notificador em envelope do bridge.

        ``WhatsAppGrupo.enviar_lote`` devolve uma lista, enquanto doubles do
        seam normalmente devolvem ``{"sessao": ..., "resultados": [...]}``.
        Uma lista só ganha sessão ``ok`` quando todos os seus itens a
        confirmam; qualquer item sem sessão explícita permanece não-ACK.
        """
        if not isinstance(response, list):
            return response
        if len(response) != len(claims) or any(not isinstance(item, Mapping) for item in response):
            return {"sessao": "erro", "resultados": []}
        items = [dict(item) for item in response]
        sessao = "ok" if all(item.get("sessao") == "ok" for item in items) else "erro"
        return {"sessao": sessao, "resultados": items}

    @staticmethod
    def _index_response(response: Any, claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        if not isinstance(response, Mapping) or not isinstance(response.get("resultados"), list):
            return {}
        expected = {claim["event_id"] for claim in claims}
        items = response["resultados"]
        if len(items) != len(claims) or any(not isinstance(item, Mapping) for item in items):
            return {}
        ids = [item.get("event_id") for item in items]
        if set(ids) != expected or len(ids) != len(set(ids)):
            return {}
        return {item["event_id"]: dict(item) for item in items}

    @staticmethod
    def _valid_ack(claim: Mapping[str, Any], response: Any, item: Any) -> bool:
        return (
            isinstance(response, Mapping)
            and response.get("sessao") == "ok"
            and isinstance(item, Mapping)
            and item.get("event_id") == claim["event_id"]
            and item.get("message_id") == claim["message_id"]
            and item.get("ack") is True
            and type(item.get("status")) is int
            and item["status"] >= 2
        )

    def _pending(self, record: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return self.outbox.aplicar_resultado(
                record["event_id"], attempt_id=record["attempt_id"],
                message_id=record["message_id"], ack=False, status=None,
            )
        except (KeyError, OutboxError):
            return self.outbox.pendentes()[0] if self.outbox.pendentes() else dict(record)


Delivery = DeliveryOrchestrator
__all__ = ["Delivery", "DeliveryError", "DeliveryOrchestrator"]
