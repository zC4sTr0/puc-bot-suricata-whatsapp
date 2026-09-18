"""Lease curto e fail-closed para serializar uma rodada do Suricata.

O job tem timeout de 5 minutos; o lease de 6 minutos evita que 30 minutos
estourem o SLA. A store é injetada para manter este módulo puro e testável.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Protocol


class LeaseState(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"


@dataclass(frozen=True)
class LeaseConfig:
    minutes: int = 6

    @classmethod
    def from_env(cls) -> "LeaseConfig":
        raw = os.environ.get("SURICATA_LEASE_MINUTOS", "6")
        try:
            minutes = int(raw)
        except ValueError as exc:
            raise ValueError("SURICATA_LEASE_MINUTOS inválido") from exc
        if minutes <= 0:
            raise ValueError("SURICATA_LEASE_MINUTOS deve ser positivo")
        return cls(minutes=minutes)


class LeaseStore(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def put_if_absent(self, key: str, value: dict[str, Any]) -> bool: ...
    def delete_if_owner(self, key: str, owner: str) -> bool: ...


class Lease:
    def __init__(self, store: LeaseStore, key: str = "locks/bot.lock", *,
                 config: LeaseConfig | None = None,
                 now: Callable[[], datetime] | None = None,
                 owner: str | None = None) -> None:
        self.store = store
        self.key = key
        self.config = config or LeaseConfig.from_env()
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.owner = owner or uuid.uuid4().hex
        self._held = False

    def classify_time(self, started_at: datetime) -> LeaseState:
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        age = self._now() - started_at.astimezone(timezone.utc)
        return LeaseState.EXPIRED if age >= timedelta(minutes=self.config.minutes) else LeaseState.ACTIVE

    def acquire(self) -> bool:
        """Tenta adquirir; qualquer falha de store ou payload bloqueia a rodada."""
        try:
            current = self.store.get(self.key)
            if current is not None:
                started = _parse_started(current)
                if self.classify_time(started) is LeaseState.ACTIVE:
                    return False
                old_owner = _owner(current)
                if not self.store.delete_if_owner(self.key, old_owner):
                    return False
            value = {"owner": self.owner, "started_at": self._now().astimezone(timezone.utc).isoformat()}
            self._held = bool(self.store.put_if_absent(self.key, value))
            return self._held
        except Exception as exc:
            raise RuntimeError("falha ao verificar lease; execução bloqueada") from exc

    def release(self) -> None:
        if not self._held:
            return
        try:
            self.store.delete_if_owner(self.key, self.owner)
            self._held = False
        except Exception as exc:
            raise RuntimeError("falha ao liberar lease") from exc

    def __enter__(self) -> "Lease":
        if not self.acquire():
            raise RuntimeError("lease ocupado")
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


def _parse_started(value: dict[str, Any]) -> datetime:
    raw = value.get("started_at") or value.get("timeCreated")
    if not isinstance(raw, str):
        raise ValueError("lease sem started_at")
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _owner(value: dict[str, Any]) -> str:
    owner = value.get("owner")
    if not isinstance(owner, str) or not owner:
        raise ValueError("lease sem owner")
    return owner
