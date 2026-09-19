"""Outbox local da camada pública WhatsApp do Suricata.

A serialização é protegida por um lock de arquivo separado. Cada mutação
recarrega o snapshot enquanto mantém o lock; assim, duas instâncias não
podem sobrescrever eventos que a outra acabou de persistir.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .locking import LockError, lock_arquivo


class OutboxError(RuntimeError):
    """Transição ou estado do outbox inválido."""


ESTADOS = {"pending", "in_flight", "sent", "expirado"}
POLITICAS = {"padrao", "reenvio_idempotente"}


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise OutboxError("data ISO inválida no outbox") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _retry_fs(operation, *, deadline: float, error: str):
    """Repete operações de filesystem sujeitas a compartilhamento no Windows."""
    while True:
        try:
            return operation()
        except FileNotFoundError:
            raise
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise OutboxError(error) from exc
            time.sleep(min(0.01, max(0.001, deadline - time.monotonic())))


@contextmanager
def _lock_arquivo(path: Path, *, timeout: float = 30.0) -> Iterator[None]:
    """Compatibilidade interna: expõe o lock comum como erro de outbox."""
    try:
        with lock_arquivo(path, timeout=timeout, namespace="SuricataOutbox", recurso="outbox"):
            yield
    except LockError as exc:
        raise OutboxError(str(exc)) from exc


class Outbox:
    def __init__(
        self, path: str | Path, *, politica: str = "reenvio_idempotente", lock_timeout: float = 30.0
    ) -> None:
        if politica not in POLITICAS:
            raise ValueError("política de outbox inválida")
        if isinstance(lock_timeout, bool) or not isinstance(lock_timeout, (int, float)) or lock_timeout < 0:
            raise ValueError("timeout de lock inválido")
        self.path = Path(path)
        self.politica = politica
        self.lock_timeout = float(lock_timeout)
        self._lock_path = self.path.with_name(f".{self.path.name}.lock")
        self._eventos: dict[str, dict[str, Any]] = {}
        # Initial loading must use the same lock as mutations. Otherwise a
        # fresh process can read while another process atomically replaces the
        # snapshot (notably yielding PermissionError on Python 3.10/Windows).
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()

    def adicionar(self, evento: dict[str, Any], *, agora: datetime | None = None) -> dict[str, Any]:
        required = {"event_id", "message_id", "texto"}
        if not required <= evento.keys():
            raise OutboxError("evento sem campos obrigatórios")
        event_id = evento["event_id"]
        if not isinstance(event_id, str) or not event_id:
            raise OutboxError("event_id inválido")
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            if event_id in self._eventos:
                existing = self._eventos[event_id]
                immutable = ("message_id", "texto", "expira_em")
                if any(existing.get(key) != evento.get(key, existing.get(key)) for key in immutable):
                    raise OutboxError("event_id reutilizado com conteúdo diferente")
                return dict(existing)
            now = agora or _agora()
            expira_em = evento.get("expira_em") or _iso(now + timedelta(hours=24))
            record = {**evento, "estado": "pending", "criado_em": _iso(now), "expira_em": expira_em}
            self._validar_record(record)
            self._eventos[event_id] = record
            self._gravar()
            return dict(record)

    def transicionar(
        self, event_id: str, novo_estado: str, *, ack: bool = False, agora: datetime | None = None
    ) -> dict[str, Any]:
        if novo_estado not in ESTADOS:
            raise OutboxError("estado WhatsApp inválido")
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            record = self._eventos.get(event_id)
            if record is None:
                raise OutboxError("evento ausente no outbox")
            return self._transicionar_carregado(record, novo_estado, ack=ack, agora=agora)

    def expirar(self, *, agora: datetime | None = None) -> list[dict[str, Any]]:
        now = agora or _agora()
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            expired = []
            for _event_id, record in list(self._eventos.items()):
                if record["estado"] == "pending" and _parse_iso(record["expira_em"]) <= now:
                    expired.append(self._transicionar_carregado(record, "expirado", agora=now))
            return expired

    def reivindicar(self, event_id: str, *, agora: datetime | None = None) -> dict[str, Any]:
        now = agora or _agora()
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            record = self._eventos.get(event_id)
            if record is None:
                raise OutboxError("evento ausente no outbox")
            if record["estado"] != "pending":
                raise OutboxError("evento não está pendente")
            if self.politica == "padrao" and record.get("tentativas", 0) > 0:
                raise OutboxError("evento não é reenviável na política padrão")
            if _parse_iso(record["expira_em"]) <= now:
                return self._transicionar_carregado(record, "expirado", agora=now)
            record = self._transicionar_carregado(record, "in_flight", agora=now)
            record = {**record, "attempt_id": uuid.uuid4().hex, "tentativas": record.get("tentativas", 0) + 1}
            self._eventos[event_id] = record
            self._gravar()
            return dict(record)

    def aplicar_resultado(
        self, event_id: str, *, attempt_id: str, message_id: str, ack: bool, status: int | None
    ) -> dict[str, Any]:
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            record = self._eventos.get(event_id)
            if record is None or record.get("estado") != "in_flight":
                raise OutboxError("tentativa não está vigente")
            if record.get("attempt_id") != attempt_id or record.get("message_id") != message_id:
                raise OutboxError("resultado de tentativa obsoleta ou divergente")
            if ack and (not isinstance(status, int) or status < 2):
                raise OutboxError("ACK sem confirmação de servidor")
            # As duas políticas preservam o evento após resultado incerto;
            # somente reenvio_idempotente permite uma nova reivindicação.
            return self._transicionar_carregado(record, "sent" if ack else "pending", ack=ack)

    def recuperar_interrompidos(self, *, agora: datetime | None = None) -> list[dict[str, Any]]:
        now = agora or _agora()
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            recovered = []
            for record in list(self._eventos.values()):
                if record["estado"] == "in_flight":
                    # Recuperação nunca expira diretamente: a expiração é
                    # aplicada explicitamente no fluxo pending -> expirar.
                    recovered.append(self._transicionar_carregado(record, "pending", agora=now))
            return recovered

    def pendentes(self) -> list[dict[str, Any]]:
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            return [dict(r) for r in self._eventos.values() if r["estado"] == "pending"]

    def cortar_apos_21h(
        self, *, agora: datetime, autorizados: set[str] | None = None,
        eventos_atuais: set[str] | None = None,
    ) -> dict[str, int]:
        """Fecha o atravessamento noturno de forma atômica e fail-closed.

        ``eventos_atuais`` é a autorização explícita, efêmera, da rodada que
        está sendo entregue. ``autorizados`` mantém o contrato legado para as
        exceções overnight já validadas pela rodada. Nenhuma flag persistida
        no JSON autoriza um registro por si só.
        """
        permitidos = set(autorizados or ()) | set(eventos_atuais or ())
        with _lock_arquivo(self._lock_path, timeout=self.lock_timeout):
            self._carregar()
            devolvidos = 0
            expirados = 0
            preservados = 0
            for record in self._eventos.values():
                if record["estado"] == "in_flight":
                    record["estado"] = "pending"
                    record["atualizado_em"] = _iso(agora)
                    devolvidos += 1
                if record["estado"] == "pending":
                    if record["event_id"] in permitidos:
                        preservados += 1
                    else:
                        record["estado"] = "expirado"
                        record["atualizado_em"] = _iso(agora)
                        expirados += 1
            self._gravar()
            return {"devolvidos": devolvidos, "expirados": expirados, "preservados": preservados}

    def _transicionar_carregado(
        self, record: dict[str, Any], novo_estado: str, *, ack: bool = False, agora: datetime | None = None
    ) -> dict[str, Any]:
        atual = record["estado"]
        permitidos = {
            "pending": {"in_flight", "expirado"},
            "in_flight": {"sent", "pending"},
            "sent": set(),
            "expirado": set(),
        }
        if novo_estado not in permitidos[atual]:
            raise OutboxError("transição de outbox inválida")
        if novo_estado == "sent" and not ack:
            raise OutboxError("sent exige ACK confirmado")
        now = agora or _agora()
        if novo_estado == "expirado" and _parse_iso(record["expira_em"]) > now:
            raise OutboxError("evento ainda não expirou")
        updated = {**record, "estado": novo_estado, "atualizado_em": _iso(now)}
        self._eventos[record["event_id"]] = updated
        self._gravar()
        return dict(updated)

    def _carregar(self) -> None:
        self._eventos = {}
        try:
            data = _retry_fs(
                lambda: self.path.read_text(encoding="utf-8"),
                deadline=time.monotonic() + self.lock_timeout,
                error="não foi possível ler o outbox",
            )
        except FileNotFoundError:
            return
        except OutboxError as exc:
            raise OutboxError("outbox inválido") from exc
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise OutboxError("outbox inválido") from exc
        if not isinstance(data, list):
            raise OutboxError("outbox inválido")
        for record in data:
            self._validar_record(record)
            event_id = record["event_id"]
            if event_id in self._eventos:
                raise OutboxError("event_id duplicado no outbox")
            self._eventos[event_id] = record

    def _gravar(self) -> None:
        for record in self._eventos.values():
            self._validar_record(record)
        deadline = time.monotonic() + self.lock_timeout
        _retry_fs(
            lambda: self.path.parent.mkdir(parents=True, exist_ok=True),
            deadline=deadline,
            error="não foi possível preparar o outbox",
        )
        fd, temp_name = _retry_fs(
            lambda: tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent),
            deadline=deadline,
            error="não foi possível criar a geração temporária do outbox",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(list(self._eventos.values()), handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                _retry_fs(handle.flush, deadline=deadline, error="não foi possível gravar o outbox")
                _retry_fs(lambda: os.fsync(handle.fileno()), deadline=deadline, error="não foi possível sincronizar o outbox")
            _retry_fs(
                lambda: os.replace(temp_name, self.path),
                deadline=deadline,
                error="não foi possível substituir o outbox",
            )
        finally:
            try:
                _retry_fs(
                    lambda: os.unlink(temp_name),
                    deadline=deadline,
                    error="não foi possível limpar a geração temporária do outbox",
                )
            except (FileNotFoundError, OutboxError):
                pass

    def _validar_record(self, record: dict[str, Any]) -> None:
        required = {"event_id", "message_id", "texto", "estado", "criado_em", "expira_em"}
        if not isinstance(record, dict) or not required <= record.keys():
            raise OutboxError("registro de outbox incompleto")

        for field in ("event_id", "message_id", "texto", "estado", "criado_em", "expira_em"):
            if not isinstance(record[field], str) or not record[field]:
                raise OutboxError(f"campo de outbox inválido: {field}")
        if record["estado"] not in ESTADOS:
            raise OutboxError("estado de outbox proibido")
        _parse_iso(record["criado_em"])
        _parse_iso(record["expira_em"])

        atualizado_em = record.get("atualizado_em")
        if atualizado_em is not None:
            if not isinstance(atualizado_em, str) or not atualizado_em:
                raise OutboxError("campo de outbox inválido: atualizado_em")
            _parse_iso(atualizado_em)
        attempt_id = record.get("attempt_id")
        if attempt_id is not None and (not isinstance(attempt_id, str) or not attempt_id):
            raise OutboxError("campo de outbox inválido: attempt_id")
        tentativas = record.get("tentativas")
        if tentativas is not None and (
            isinstance(tentativas, bool) or not isinstance(tentativas, int) or tentativas < 1
        ):
            raise OutboxError("campo de outbox inválido: tentativas")


__all__ = ["Outbox", "OutboxError"]
