"""Contrato injetável para leitura pública do Canvas, sem efeitos de rede.

O módulo define o shape consumido pelo orquestrador. ``CanvasPublicAdapter`` só
faz a ponte para a interface já existente de ``CanvasClient``; o transporte
continua sendo responsabilidade dele. ``FakeCanvasAdapter`` é totalmente
in-memory e é o double recomendado para testes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
import math
import re
from typing import Any, Mapping, Protocol, Sequence


_PUBLIC_PLANNER_FIELDS = frozenset({
    "id", "title", "name", "course_id", "course_name", "context_name",
    "start_at", "end_at", "due_at", "html_url", "url",
})
_PUBLIC_ASSIGNMENT_FIELDS = frozenset({
    "id", "name", "points_possible", "description", "due_at", "unlock_at",
    "lock_at", "quiz_id", "html_url", "url", "course_id",
})
_FORBIDDEN_NESTED_FIELDS = frozenset({
    "cookie", "credential", "credentials", "identity", "jwt", "password",
    "secret", "session", "submission", "token", "user", "user_id",
})


@dataclass(frozen=True)
class PublicResponse:
    """Resposta pública com status explícito; vazio não significa sucesso."""

    status: int | None
    items: tuple[dict[str, Any], ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class PublicCollection:
    """Resultado da coleta; ``usavel`` aplica a política fail-closed."""

    planner: PublicResponse
    assignments: dict[str, PublicResponse] = field(default_factory=dict)

    @property
    def usavel(self) -> bool:
        return self.planner.status == 200 and all(
            response.status == 200 for response in self.assignments.values()
        )


class PublicCanvasSource(Protocol):
    def planner_publico(self) -> PublicResponse: ...

    def assignments_publicos(self, course_id: str) -> PublicResponse: ...


def unavailable_planner() -> PublicResponse:
    """Retorna o estado padrão quando não existe planner público disponível."""
    return PublicResponse(status=None, error="planner_unavailable")


def _reject_nested_private_data(value: Any) -> None:
    if isinstance(value, Mapping):
        for name, nested in value.items():
            normalized_name = re.sub(r"[^a-z0-9]", "", str(name).lower())
            if (
                normalized_name in _FORBIDDEN_NESTED_FIELDS
                or any(term in normalized_name for term in ("token", "session", "submission", "identity"))
            ):
                raise ValueError("campo privado aninhado")
            _reject_nested_private_data(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_nested_private_data(nested)


def _clean_text(value: Any) -> str:
    _reject_nested_private_data(value)
    if isinstance(value, (Mapping, list, tuple)):
        raise TypeError("texto público deve ser escalar")
    return unescape(re.sub(r"<[^>]*>", "", str(value or ""))).strip()


def _scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int, float)):
        return value
    _reject_nested_private_data(value)
    raise TypeError("campo público deve ser escalar")


def _normalize_item(raw: Any, allowed: frozenset[str]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raw = {name: getattr(raw, name) for name in allowed if hasattr(raw, name)}
    if not isinstance(raw, Mapping):
        raise TypeError("item público inválido")
    identifier = raw.get("id")
    if identifier is None or not str(identifier).strip():
        raise ValueError("item público sem id")
    normalized: dict[str, Any] = {}
    for name in sorted(allowed):
        if name not in raw or raw[name] is None:
            continue
        value = raw[name]
        if name in {"name", "title", "description", "course_name", "context_name"}:
            value = _clean_text(value)
            if name in {"description", "course_name", "context_name"} and not value:
                continue
        elif name == "points_possible":
            if isinstance(value, bool):
                raise ValueError("points_possible inválido")
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError("points_possible inválido")
        else:
            value = _scalar(value)
        normalized[name] = value
    normalized["id"] = str(identifier).strip()
    return {name: normalized[name] for name in sorted(normalized)}


def _normalize_response(raw: Any, allowed: frozenset[str]) -> PublicResponse:
    status = raw.get("status") if isinstance(raw, Mapping) else getattr(raw, "status", None)
    items = raw.get("items", ()) if isinstance(raw, Mapping) else getattr(raw, "items", ())
    error = raw.get("error") if isinstance(raw, Mapping) else getattr(raw, "error", None)
    if isinstance(status, bool) or (status is not None and not isinstance(status, int)):
        return PublicResponse(None, error="invalid_status")
    if not isinstance(items, (list, tuple)):
        return PublicResponse(status, error="invalid_items")
    try:
        normalized = tuple(sorted(
            (_normalize_item(item, allowed) for item in items),
            key=lambda item: (item["id"], repr(item)),
        ))
    except (TypeError, ValueError, OverflowError):
        return PublicResponse(status, error="invalid_payload")
    if error is not None:
        try:
            error = str(_scalar(error))
        except (TypeError, ValueError):
            return PublicResponse(status, error="invalid_payload")
    return PublicResponse(status, normalized, error)


class CanvasPublicAdapter:
    """Adapta somente a interface pública já existente de ``CanvasClient``.

    O cliente atual não possui rota de planner público. Por isso o método
    ``planner_publico`` é deliberadamente indisponível, e ``coletar`` não
    consulta assignments enquanto essa etapa não tiver status 200.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    def planner_publico(self) -> PublicResponse:
        return unavailable_planner()

    def assignments_publicos(self, course_id: str) -> PublicResponse:
        try:
            return _normalize_response(self._client.assignments(str(course_id)), _PUBLIC_ASSIGNMENT_FIELDS)
        except Exception:
            return PublicResponse(None, error="assignments_unavailable")

    def coletar(self, course_ids: Sequence[str]) -> PublicCollection:
        planner = self.planner_publico()
        if planner.status != 200:
            return PublicCollection(planner)
        assignments = {
            course_id: self.assignments_publicos(course_id)
            for course_id in sorted(dict.fromkeys(str(value) for value in course_ids))
        }
        return PublicCollection(planner, assignments)


class FakeCanvasAdapter(CanvasPublicAdapter):
    """Fonte in-memory para testes; não aceita nem cria transporte HTTP."""

    def __init__(self, *, planner: Any | None = None, assignments: Mapping[str, Any] | None = None) -> None:
        self._planner = planner if planner is not None else unavailable_planner()
        self._assignments = dict(assignments or {})
        self.calls: list[tuple[str, str | None]] = []

    def planner_publico(self) -> PublicResponse:
        self.calls.append(("planner", None))
        return _normalize_response(self._planner, _PUBLIC_PLANNER_FIELDS)

    def assignments_publicos(self, course_id: str) -> PublicResponse:
        course_id = str(course_id)
        self.calls.append(("assignments", course_id))
        return _normalize_response(self._assignments.get(course_id, {"status": 200, "items": []}), _PUBLIC_ASSIGNMENT_FIELDS)


__all__ = [
    "CanvasPublicAdapter", "FakeCanvasAdapter", "PublicCanvasSource",
    "PublicCollection", "PublicResponse", "unavailable_planner",
]
