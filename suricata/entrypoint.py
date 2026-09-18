"""Entrypoint fail-closed do runtime somente leitura do Suricata."""
from __future__ import annotations

import json
import math
import sys
from typing import Any, Callable, Mapping, Sequence

from .adapter import CanvasPublicAdapter
from .application import executar_sombra
from .canvas import CanvasClient, _normalize_origin
from .estado import EstadoLocal

# "rodada" é o caminho de produção (Cloud Run); "sentinela" é o caminho legado de sombra.
# "demo" é a probe funcional offline (fixtures congeladas, sem Canvas/estado/entrega).
_MODES = {"shadow", "sentinela", "rodada", "grupos", "teste-envio", "demo"}

_AJUDA = """uso: python -m suricata --mode MODO [--config ARQUIVO]

modos:
  shadow        probe local sem efeitos (zero-config)
  demo          rodada offline com fixtures congeladas; entrega desligada
  sentinela     sombra funcional com --config (legado)
  rodada        caminho canônico de produção (configuração via ambiente)
  grupos        inventário read-only da sessão
  teste-envio   efeito externo; proibido em validação

variáveis de ambiente: veja .env.example e docs/CONFIGURATION.md
matriz de validação local: veja CONTRIBUTING.md
"""


def _emit(record: Mapping[str, Any]) -> None:
    print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))


def _parse_args(argv: Sequence[str]) -> tuple[str | None, str | None, str | None]:
    mode: str | None = None
    config: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg not in {"--mode", "--config"} or i + 1 >= len(argv):
            return None, None, "argumentos inválidos (use --mode MODO e/ou --config ARQUIVO; veja --help)"
        value = argv[i + 1]
        if arg == "--mode":
            if mode is not None:
                return None, None, "argumentos inválidos (use --mode MODO e/ou --config ARQUIVO; veja --help)"
            mode = value
        else:
            if config is not None:
                return None, None, "argumentos inválidos (use --mode MODO e/ou --config ARQUIVO; veja --help)"
            config = value
        i += 2
    if mode is None:
        return None, None, "modo ausente (veja --help)"
    if mode not in _MODES:
        return None, None, "modo inválido (veja --help)"
    return mode, config, None


def _read_explicit_config(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _validated_config(value: dict[str, Any]) -> tuple[list[str], dict[str, Any], str | None] | None:
    # Segredo por argv/arquivo é rejeitado; CanvasClient resolve apenas o env
    # próprio no interior do cliente e nunca devolve esse valor ao relatório.
    if any(str(key).casefold() in {"token", "access_token", "authorization", "secret"} for key in value):
        return None
    ofertas = value.get("ofertas")
    if not isinstance(ofertas, list) or not ofertas:
        return None
    if any(not isinstance(oferta, str) or not oferta.strip() for oferta in ofertas):
        return None
    canvas = value.get("canvas", {})
    if not isinstance(canvas, dict):
        return None
    origin = canvas.get("origin")
    if origin is not None:
        try:
            origin = _normalize_origin(origin, require_allowlist=True)
        except (TypeError, ValueError):
            return None
    timeout = canvas.get("timeout", 20.0)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        return None
    if not math.isfinite(timeout):
        return None
    state = value.get("estado")
    if state is not None and not isinstance(state, dict):
        return None
    state_path = state.get("path") if state is not None else value.get("state_path")
    if state is not None and "path" in state and "state_path" in value:
        return None
    if state_path is not None and (not isinstance(state_path, str) or not state_path.strip()):
        return None
    return (list(dict.fromkeys(oferta.strip() for oferta in ofertas)),
            {"origin": origin, "timeout": float(timeout)}, state_path)


class _InjectedClientAdapter:
    """Adapter explícito para doubles locais; nunca é usado no caminho real."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def planner_publico(self) -> dict[str, Any]:
        # Um double de cliente injetado representa uma fonte já selecionada;
        # o caminho de produção usa CanvasPublicAdapter, cujo planner é fechado.
        status = getattr(self._client, "status", 200)
        # Compatibilidade limitada para doubles antigos que modelam o erro na
        # oferta; erros de serviço continuam sendo barreira de planner.
        planner_status = status if isinstance(status, int) and status >= 500 else 200
        return {"status": planner_status, "items": []}

    def assignments_publicos(self, oferta: str) -> dict[str, Any]:
        response = self._client.assignments(oferta)
        return {
            "status": getattr(response, "status", None),
            "items": tuple(getattr(response, "items", ()) or ()),
        }


def _adapter_for(client: Any, *, injected: bool) -> Any:
    """Aceita adapter injetado; cliente real sempre passa pelo adapter seguro."""
    if client is None:
        raise ValueError("adapter indisponível")
    if callable(getattr(client, "coletar", None)):
        return client
    return _InjectedClientAdapter(client) if injected else CanvasPublicAdapter(client)


def executar_config(
    config: dict[str, Any],
    *,
    client_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    validado = _validated_config(config)
    if validado is None:
        raise ValueError("configuração inválida")
    ofertas, canvas_config, state_path = validado
    kwargs: dict[str, Any] = {"timeout": canvas_config["timeout"]}
    if canvas_config["origin"] is not None:
        kwargs["origin"] = canvas_config["origin"]
    # Nunca passe token explicitamente: CanvasClient lê apenas seu mecanismo
    # interno de credencial e mantém o header fora do domínio/report.
    client_factory_provided = client_factory is not None
    client = (client_factory or CanvasClient)(**kwargs)
    state_writer = EstadoLocal(state_path) if state_path is not None else None
    return executar_sombra(_adapter_for(client, injected=client_factory_provided), ofertas, state_writer=state_writer)


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[..., CanvasClient] | None = None,
) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if {"--help", "-h"} & set(argumentos):
        print(_AJUDA)
        return 0
    mode, config_path, error = _parse_args(argumentos)
    if error:
        _emit({"status": "error", "error": error})
        return 2
    if mode == "demo":
        from .demo import main as demo_main
        return demo_main()
    if mode == "rodada":
        from .rodada import main as rodada_main
        return rodada_main()
    if mode == "grupos":
        from .grupos import main as grupos_main
        return grupos_main()
    if mode == "teste-envio":
        from .teste_envio import main as teste_main
        return teste_main()
    if mode == "shadow":
        _emit({"mode": "shadow", "status": "ok", "adapter": "none"})
        return 0
    if config_path is None:
        _emit({"mode": "sentinela", "status": "error", "error": "configuração ausente (use --config com um JSON como suricata/config.example.json)"})
        return 2
    config = _read_explicit_config(config_path)
    if config is None:
        _emit({"mode": "sentinela", "status": "error", "error": "configuração inválida"})
        return 2
    try:
        report = executar_config(config, client_factory=client_factory)
    except ValueError as exc:
        _emit({"mode": "sentinela", "status": "error", "error": str(exc)})
        return 2
    except Exception:
        _emit({"mode": "sentinela", "status": "error", "error": "Canvas indisponível"})
        return 3
    _emit({"mode": "sentinela", "status": "ok", "relatorio": report})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
