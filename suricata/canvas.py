"""Cliente Canvas público, somente GET, sem DTOs de estado pessoal."""
from __future__ import annotations

import html
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Any, Callable, Mapping, Sequence

ORIGIN = "https://pucminas.instructure.com"
API = "/api/v1"

@dataclass(frozen=True)
class Route:
    name: str
    path: str
    method: str = "GET"
    params: tuple[str, ...] = ()

ROUTES = {
    "assignments": Route("assignments", f"{API}/courses/{{course_id}}/assignments", params=("include[]", "per_page")),
    "announcements": Route("announcements", f"{API}/announcements", params=("context_codes[]", "start_date", "per_page")),
    "courses": Route("courses", f"{API}/courses", params=("enrollment_state", "per_page")),
}
ROUTES["anuncios"] = ROUTES["announcements"]

class CanvasResponseKind(str, Enum):
    OK = "ok"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    TRANSPORT_ERROR = "transport_error"
    INVALID_PAYLOAD = "invalid_payload"

@dataclass(frozen=True)
class PublicAssignment:
    id: str
    name: str
    points_possible: float | None = None
    description: str = ""
    due_at: str | None = None
    unlock_at: str | None = None
    lock_at: str | None = None
    quiz_id: str | None = None
    submission_types: tuple[str, ...] = ()
    is_quiz_lti: bool = False
    html_url: str = ""

@dataclass(frozen=True)
class PublicCourse:
    id: str
    name: str

@dataclass(frozen=True)
class PublicAnnouncement:
    id: str
    title: str
    message: str
    posted_at: str | None = None
    context_code: str = ""
    html_url: str = ""

@dataclass(frozen=True)
class CanvasResponse:
    kind: CanvasResponseKind
    status: int | None
    items: tuple[PublicAssignment | PublicAnnouncement | PublicCourse, ...] = ()
    error: str | None = None

Transport = Callable[[str, str, Mapping[str, str], float], tuple[int, Mapping[str, str], Any]]

class CanvasClient:
    """Transporte injetável; token é usado somente no header e nunca no retorno."""
    def __init__(self, token: str | None = None, *, origin: str = ORIGIN,
                 timeout: float = 20.0, transport: Transport | None = None) -> None:
        if timeout <= 0:
            raise ValueError("timeout deve ser positivo")
        self._token = token if token is not None else os.environ.get("SURICATA_CANVAS_TOKEN", "")
        self.origin = _normalize_origin(origin)
        self.timeout = timeout
        self._transport = transport or _urllib_transport
        self.requisicoes = 0

    def assignments(self, course_id: str) -> CanvasResponse:
        route = ROUTES["assignments"]
        query = {"include[]": "all_dates", "per_page": "100"}
        return self._get(route, route.path.format(course_id=urllib.parse.quote(str(course_id), safe="")), query, _assignment)

    def courses(self) -> CanvasResponse:
        """Ofertas ativas do titular (só id e nome)."""
        route = ROUTES["courses"]
        return self._get(route, route.path, {"enrollment_state": "active", "per_page": "100"}, _course)

    def announcements(self, context_codes: Sequence[str], start_date: str) -> CanvasResponse:
        if not context_codes or not start_date:
            raise ValueError("context_codes e start_date são obrigatórios")
        query = [("context_codes[]", code) for code in context_codes]
        query += [("start_date", start_date), ("per_page", "100")]
        return self._get(ROUTES["announcements"], ROUTES["announcements"].path, query, _announcement)

    def _get(self, route: Route, path: str, query: Mapping[str, str] | Sequence[tuple[str, str]], converter: Callable[[Mapping[str, Any]], Any]) -> CanvasResponse:
        if route.method != "GET":
            raise AssertionError("rota pública não pode alterar dados")
        url = f"{self.origin}{path}?{urllib.parse.urlencode(query)}"
        headers = {"Accept": "application/json"}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        self.requisicoes += 1
        try:
            status, _, body = self._transport("GET", url, headers, self.timeout)
        except json.JSONDecodeError:
            return CanvasResponse(CanvasResponseKind.INVALID_PAYLOAD, None)
        except Exception as exc:
            return CanvasResponse(CanvasResponseKind.TRANSPORT_ERROR, None, error=type(exc).__name__)
        kind = classify_status(status)
        if kind is CanvasResponseKind.INVALID_PAYLOAD:
            return CanvasResponse(kind, None)
        if kind is not CanvasResponseKind.OK:
            return CanvasResponse(kind, status)
        if not isinstance(body, list):
            return CanvasResponse(CanvasResponseKind.INVALID_PAYLOAD, status)
        try:
            return CanvasResponse(kind, status, _itens_do_payload(body, converter))
        except (TypeError, ValueError, KeyError):
            return CanvasResponse(CanvasResponseKind.INVALID_PAYLOAD, status)


def _itens_do_payload(
    body: list[Any], converter: Callable[[Mapping[str, Any]], Any]
) -> tuple[Any, ...]:
    """Converte um payload Canvas validado sem expor o formato HTTP ao domínio."""
    itens = []
    for item in body:
        if not isinstance(item, Mapping):
            raise TypeError("item Canvas não é um objeto")
        itens.append(converter(item))
    return tuple(itens)

def classify_status(status: Any) -> CanvasResponseKind:
    if isinstance(status, bool) or not isinstance(status, int):
        return CanvasResponseKind.INVALID_PAYLOAD
    if status == 200: return CanvasResponseKind.OK
    if status == 401: return CanvasResponseKind.UNAUTHORIZED
    if status == 403: return CanvasResponseKind.FORBIDDEN
    if status == 404: return CanvasResponseKind.NOT_FOUND
    if status == 429: return CanvasResponseKind.RATE_LIMITED
    if 400 <= status < 500: return CanvasResponseKind.CLIENT_ERROR
    if status >= 500: return CanvasResponseKind.SERVER_ERROR
    return CanvasResponseKind.CLIENT_ERROR


def _normalize_origin(origin: str, *, require_allowlist: bool = True) -> str:
    """Normalize the only permitted Canvas origin.

    ``require_allowlist`` remains accepted for source compatibility, but the
    allowlist is always enforced; an unauthenticated request must not widen
    the SSRF boundary.
    """
    parsed = urllib.parse.urlsplit(origin)
    valid = (
        parsed.scheme.lower() == "https"
        and parsed.hostname == urllib.parse.urlsplit(ORIGIN).hostname
        and parsed.username is None
        and parsed.password is None
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
    )
    try:
        port = parsed.port
    except ValueError:
        port = None
        valid = False
    valid = valid and port in (None, 443)
    if not valid:
        raise ValueError("origem Canvas inválida")
    if valid:
        return ORIGIN
    return origin.rstrip("/")

def _clean(value: Any) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or ""))).strip()

def _required_id(item: Mapping[str, Any]) -> str:
    value = item["id"]
    if value is None or not str(value).strip():
        raise ValueError("id Canvas ausente ou vazio")
    return str(value)


def _assignment(item: Mapping[str, Any]) -> PublicAssignment:
    points = _points_possible(item.get("points_possible"))
    return PublicAssignment(_required_id(item), _clean(item.get("name")), points,
        _clean(item.get("description")), item.get("due_at"), item.get("unlock_at"), item.get("lock_at"),
        str(item["quiz_id"]) if item.get("quiz_id") is not None else None,
        tuple(str(t) for t in (item.get("submission_types") or ()) if isinstance(t, str)),
        item.get("is_quiz_lti_assignment") is True,
        _html_url(item.get("html_url")))


def _html_url(value: Any) -> str:
    """Só links do próprio Canvas, sem query nem fragmento (URLs assinadas ficam fora)."""
    if not isinstance(value, str):
        return ""
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname != urllib.parse.urlsplit(ORIGIN).hostname:
        return ""
    return f"{ORIGIN}{parsed.path}"


def _course(item: Mapping[str, Any]) -> PublicCourse:
    return PublicCourse(_required_id(item), _clean(item.get("name")))


def _points_possible(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("points_possible Canvas deve ser numérico")
    try:
        points = float(value)
    except (OverflowError, ValueError, TypeError) as exc:
        raise ValueError("points_possible Canvas inválido") from exc
    if not math.isfinite(points) or points < 0:
        raise ValueError("points_possible Canvas deve ser finito e não negativo")
    return points

def _announcement(item: Mapping[str, Any]) -> PublicAnnouncement:
    return PublicAnnouncement(_required_id(item), _clean(item.get("title")), _clean(item.get("message")),
                              item.get("posted_at"), str(item.get("context_code") or ""),
                              _html_url(item.get("html_url")))

def _urllib_transport(method: str, url: str, headers: Mapping[str, str], timeout: float) -> tuple[int, Mapping[str, str], Any]:
    if method != "GET":
        raise ValueError("CanvasClient aceita somente GET")
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, response_headers, raw = response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        status, response_headers, raw = error.code, error.headers, error.read()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = None
    return status, response_headers, body
