"""Estado operacional local e somente da Suricata.

O módulo não conhece Canvas, WhatsApp, Telegram ou credenciais. O estado é
formado por um snapshot JSON (heartbeat/memória) e um diário JSONL append-only.
Escritas usam lock local, arquivo temporário e ``os.replace`` para que uma
interrupção não deixe um JSON parcial.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


class EstadoError(ValueError):
    """Entrada ou estado operacional inválido."""


_STATUS = frozenset({
    "ok", "degradado", "erro", "ausente", "indisponivel", "parcial",
    "concluida", "vazio_confirmado", "acesso_negado",
})
_FORBIDDEN = frozenset({
    "token", "access_token", "authorization", "cookie", "cookies", "session",
    "sessao", "qr", "pairing_code", "senha", "password", "secret", "jwt",
    "nota", "entrega", "submission", "atraso", "jid", "telefone", "nome_pessoa",
})
_SAFE_FIELDS = frozenset({"status", "erro", "tentativas", "contagens", "rodada_em"})


def _iso(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise EstadoError("momento inválido")
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def _chave_texto(value: Any, nome: str) -> str:
    if not isinstance(value, str) or not value or "|" in value or "\n" in value or "\r" in value:
        raise EstadoError(f"{nome} inválido")
    return value


def dedup_key(item_id: str, versao: str, transicao: str) -> str:
    """Identidade estável de item, versão e transição operacional."""
    return "|".join((_chave_texto(item_id, "item_id"), _chave_texto(versao, "versão"), _chave_texto(transicao, "transição")))


def _procurar_proibido(value: Any, caminho: str = "") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in _FORBIDDEN:
                raise EstadoError("campo não permitido no estado operacional")
            _procurar_proibido(child, f"{caminho}.{key}")
    elif isinstance(value, (list, tuple)):
        for child in value:
            _procurar_proibido(child, caminho)


def sanitizar_status_operacional(status: Mapping[str, Any]) -> dict[str, Any]:
    """Mantém somente um status operacional curto e sem dados sensíveis."""
    if not isinstance(status, Mapping):
        raise EstadoError("status operacional deve ser objeto")
    seguro = {key: value for key, value in status.items() if str(key).casefold() not in _FORBIDDEN}
    desconhecidos = set(seguro) - _SAFE_FIELDS
    if desconhecidos:
        raise EstadoError("campo não permitido no status operacional")
    resultado: dict[str, Any] = {}
    valor = seguro.get("status", "ok")
    if valor not in _STATUS:
        raise EstadoError("status operacional inválido")
    resultado["status"] = valor
    if "erro" in seguro:
        erro = seguro["erro"]
        if not isinstance(erro, str) or not erro or len(erro) > 200 or re.search(r"[\x00-\x1f\x7f-\x9f]", erro):
            raise EstadoError("erro operacional inválido")
        resultado["erro"] = erro
    if "tentativas" in seguro:
        tentativas = seguro["tentativas"]
        if isinstance(tentativas, bool) or not isinstance(tentativas, int) or tentativas < 0:
            raise EstadoError("tentativas inválidas")
        resultado["tentativas"] = tentativas
    if "contagens" in seguro:
        contagens = seguro["contagens"]
        _procurar_proibido(contagens)
        if not isinstance(contagens, Mapping) or any(
            not isinstance(k, str) or not isinstance(v, int) or isinstance(v, bool) or v < 0
            for k, v in contagens.items()
        ):
            raise EstadoError("contagens inválidas")
        resultado["contagens"] = dict(contagens)
    if "rodada_em" in seguro:
        resultado["rodada_em"] = _chave_texto(seguro["rodada_em"], "rodada_em")
    return resultado


@contextmanager
def _lock(path: Path, timeout: float = 10.0) -> Iterator[None]:
    """Lock por processo, com a primitiva nativa disponível no host."""
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    handle = path.open("a+b")
    try:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise EstadoError("timeout ao adquirir lock do estado") from exc
                    time.sleep(0.01)
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise EstadoError("timeout ao adquirir lock do estado") from exc
                    time.sleep(0.01)
        yield
    finally:
        if os.name == "nt":
            import msvcrt
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _escrever_bytes_atomico(caminho: Path, payload: bytes) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario: str | None = None
    fd, temporario = tempfile.mkstemp(prefix=f".{caminho.name}.", suffix=".tmp", dir=caminho.parent)
    try:
        with os.fdopen(fd, "wb") as saida:
            saida.write(payload)
            saida.flush()
            os.fsync(saida.fileno())
        os.replace(temporario, caminho)
        temporario = None
    finally:
        if temporario is not None:
            Path(temporario).unlink(missing_ok=True)


def escrever_json_atomico(caminho: str | Path, valor: Any) -> None:
    caminho = Path(caminho)
    payload = json.dumps(valor, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    _escrever_bytes_atomico(caminho, payload.encode("utf-8"))


def _ler_jsonl(caminho: Path) -> list[dict[str, Any]]:
    if not caminho.exists():
        return []
    registros = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            valor = json.loads(linha)
            if not isinstance(valor, dict):
                raise EstadoError("linha JSONL inválida")
            registros.append(valor)
    return registros


def anexar_jsonl_atomico(caminho: str | Path, registros: Iterable[Mapping[str, Any]]) -> int:
    """Acrescenta registros sem reescrever o histórico lógico."""
    caminho = Path(caminho)
    novos = [dict(registro) for registro in registros]
    if not novos:
        return 0
    with _lock(caminho.with_name(f".{caminho.name}.lock")):
        antigos = _ler_jsonl(caminho)
        payload = "".join(
            json.dumps(registro, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
            for registro in antigos + novos
        )
        _escrever_bytes_atomico(caminho, payload.encode("utf-8"))
    return len(novos)


class EstadoLocal:
    """Persistência local isolada para memória de grupo e operação."""

    def __init__(self, raiz: str | Path):
        self.raiz = Path(raiz)
        self.grupo = self.raiz / "grupo"
        self.heartbeat_path = self.raiz / "heartbeat.json"
        self.memoria_path = self.grupo / "sentinela.json"
        self.dedup_path = self.grupo / "dedup.jsonl"
        self.diario_path = self.grupo / "diario.jsonl"

    def _ler_json(self, caminho: Path) -> dict[str, Any]:
        if not caminho.exists():
            return {}
        valor = json.loads(caminho.read_text(encoding="utf-8"))
        if not isinstance(valor, dict):
            raise EstadoError("snapshot JSON inválido")
        return valor

    def ler_heartbeat(self) -> dict[str, Any]:
        return self._ler_json(self.heartbeat_path)

    def atualizar_heartbeat(self, *, saudavel: bool, agora: datetime, contagens: Mapping[str, int] | None = None, status: str = "ok", erro: str | None = None) -> dict[str, Any]:
        with _lock(self.heartbeat_path.with_name(f".{self.heartbeat_path.name}.lock")):
            atual = self._ler_json(self.heartbeat_path)
            atual.update(sanitizar_status_operacional({"status": status, **({"erro": erro} if erro is not None else {}), **({"contagens": contagens} if contagens is not None else {}), "rodada_em": _iso(agora)}))
            if saudavel:
                atual["sentinela_ok_em"] = _iso(agora)
            _procurar_proibido(atual)
            escrever_json_atomico(self.heartbeat_path, atual)
        return dict(atual)

    def ler_memoria_grupo(self) -> dict[str, Any]:
        return self._ler_json(self.memoria_path)

    def registrar_memoria_grupo(self, memoria: Mapping[str, Any]) -> dict[str, Any]:
        _procurar_proibido(memoria)
        atual = dict(memoria)
        if "linha_de_base_em" not in atual:
            raise EstadoError("memória do grupo exige linha_de_base_em")
        with _lock(self.memoria_path.with_name(f".{self.memoria_path.name}.lock")):
            escrever_json_atomico(self.memoria_path, atual)
        return atual

    def atualizar_memoria_grupo(self, **campos: Any) -> dict[str, Any]:
        """Faz merge serializado na memória pública do grupo."""
        _procurar_proibido(campos)
        with _lock(self.memoria_path.with_name(f".{self.memoria_path.name}.lock")):
            atual = self._ler_json(self.memoria_path)
            atual.update(campos)
            escrever_json_atomico(self.memoria_path, atual)
        return dict(atual)

    def registrar_anuncio_visto(self, anuncio_id: str, *, visto_em: datetime) -> dict[str, Any]:
        """Registra a observação de anúncio sem misturá-la à audiência pessoal."""
        anuncio_id = _chave_texto(anuncio_id, "anuncio_id")
        with _lock(self.memoria_path.with_name(f".{self.memoria_path.name}.lock")):
            atual = self._ler_json(self.memoria_path)
            vistos = atual.get("anuncios_vistos", {})
            if not isinstance(vistos, dict):
                raise EstadoError("anuncios_vistos inválido")
            vistos = dict(vistos)
            vistos.setdefault(anuncio_id, _iso(visto_em))
            atual["anuncios_vistos"] = vistos
            escrever_json_atomico(self.memoria_path, atual)
        return dict(atual)

    def ja_deduplicado(self, chave: str) -> bool:
        return any(registro.get("dedup_key") == chave for registro in _ler_jsonl(self.dedup_path))

    def registrar_dedup(self, registro: Mapping[str, Any]) -> bool:
        item = dict(registro)
        chave = item.get("dedup_key") or dedup_key(item["item_id"], item["versao"], item["transicao"])
        item["dedup_key"] = chave
        _procurar_proibido(item)
        lock_path = self.dedup_path.with_name(f".{self.dedup_path.name}.lock")
        with _lock(lock_path):
            if any(registro.get("dedup_key") == chave for registro in _ler_jsonl(self.dedup_path)):
                return False
            antigos = _ler_jsonl(self.dedup_path)
            payload = "".join(
                json.dumps(registro, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
                for registro in antigos + [item]
            )
            _escrever_bytes_atomico(self.dedup_path, payload.encode("utf-8"))
            return True

    def registrar_diario(self, registro: Mapping[str, Any]) -> int:
        _procurar_proibido(registro)
        return anexar_jsonl_atomico(self.diario_path, [registro])


# Nomes curtos para consumidores que preferem o contrato em inglês.
atomic_json_write = escrever_json_atomico
atomic_jsonl_append = anexar_jsonl_atomico

# Alias explícito para consumidores que tratam o módulo como o estado do
# produto, sem obrigar a conhecer o nome de armazenamento local.
EstadoSuricata = EstadoLocal
EstadoOperacional = EstadoLocal

__all__ = ["EstadoError", "EstadoLocal", "EstadoSuricata", "EstadoOperacional", "dedup_key", "sanitizar_status_operacional", "escrever_json_atomico", "anexar_jsonl_atomico"]
