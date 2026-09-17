"""CAS isolado da sessão WhatsApp do Suricata.

O módulo usa apenas a CLI externa ``gcloud``. A CLI resolve credenciais por
ADC/metadata conforme o ambiente; nenhum token é lido ou manipulado aqui.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


BUCKET_URI = "gs://suricata-college-20260913-estado"
AUTH_OBJECT_URI = f"{BUCKET_URI}/whatsapp/auth.json"
_GCLOUD_ENV_KEYS = ("PATH", "HOME", "USERPROFILE", "CLOUDSDK_CONFIG")


class StorageError(RuntimeError):
    """Erro sanitizado do armazenamento, sem conteúdo da sessão."""


class CASConflict(StorageError):
    """A geração esperada não corresponde à geração atual."""


class ReadBackError(StorageError):
    """A escrita não pôde ser confirmada por read-back."""


@dataclass(frozen=True)
class AuthSnapshot:
    value: dict[str, Any] | None
    generation: str | None


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


class SuricataSessionStorage:
    """Lê/grava apenas ``whatsapp/auth.json`` no bucket do Suricata.

    ``run`` existe para testes unitários; em produção o padrão é
    :func:`subprocess.run`, sem shell. O payload JSON sempre vai por stdin,
    nunca por argv ou saída de log.
    """

    def __init__(
        self,
        *,
        gcloud: str | None = None,
        timeout: float = 30.0,
        run: Runner = subprocess.run,
    ) -> None:
        self.gcloud = gcloud or os.environ.get("SURICATA_GCLOUD_BIN", "gcloud")
        self.timeout = timeout
        self._run = run

    def read_auth(self) -> AuthSnapshot:
        """Retorna a sessão e sua geração; ausência é ``(None, None)``."""
        metadata = self._invoke(
            [self.gcloud, "storage", "objects", "describe", AUTH_OBJECT_URI, "--format=json"],
            missing_ok=True,
        )
        if metadata is None:
            return AuthSnapshot(None, None)
        generation = self._parse_generation(metadata)
        payload = self._invoke(
            [self.gcloud, "storage", "cat", AUTH_OBJECT_URI],
        )
        value = self._parse_object(payload.stdout)

        # ``describe`` e ``cat`` são operações separadas. Revalidar depois do
        # cat impede devolver payload de uma geração diferente da anunciada;
        # a mensagem de erro não inclui o payload nem seus campos.
        after_metadata = self._invoke(
            [self.gcloud, "storage", "objects", "describe", AUTH_OBJECT_URI, "--format=json"],
            missing_ok=True,
        )
        if after_metadata is None:
            raise StorageError("objeto da sessão desapareceu durante a leitura")
        after_generation = self._parse_generation(after_metadata)
        if after_generation != generation:
            raise StorageError("leitura inconsistente da sessão WhatsApp")
        return AuthSnapshot(value, generation)

    def write_auth(
        self,
        value: dict[str, Any],
        *,
        expected_generation: str | None,
    ) -> AuthSnapshot:
        """Grava com precondição CAS explícita e confirma o conteúdo lendo-o.

        ``None`` significa criação condicional (geração zero), não sobrescrita
        incondicional. A confirmação falha se a geração não mudar ou o objeto
        lido não for igual ao objeto enviado.
        """
        if not isinstance(value, dict):
            raise TypeError("a sessão WhatsApp deve ser um objeto JSON")
        try:
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise TypeError("a sessão WhatsApp deve ser JSON serializável") from exc

        match = expected_generation if expected_generation is not None else "0"
        self._invoke(
            [
                self.gcloud,
                "storage",
                "cp",
                "-",
                AUTH_OBJECT_URI,
                f"--if-generation-match={match}",
                "--content-type=application/json",
            ],
            input=encoded,
        )
        after = self.read_auth()
        if after.value != value or after.generation is None:
            raise ReadBackError("read-back da sessão WhatsApp não confirmou a escrita")
        if expected_generation is not None and after.generation == expected_generation:
            raise ReadBackError("read-back da sessão WhatsApp não confirmou nova geração")
        return after

    def _invoke(
        self,
        argv: list[str],
        *,
        input: bytes | None = None,
        missing_ok: bool = False,
    ) -> subprocess.CompletedProcess[bytes] | None:
        try:
            result = self._run(
                argv,
                input=input,
                capture_output=True,
                timeout=self.timeout,
                check=False,
                env=_gcloud_environment(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StorageError("falha na chamada externa do armazenamento") from exc
        if result.returncode == 0:
            return result
        if missing_ok and _looks_missing(result.stderr):
            return None
        if "412" in _safe_text(result.stderr) or "precondition" in _safe_text(result.stderr).lower():
            raise CASConflict("conflito de geração da sessão WhatsApp")
        raise StorageError("gcloud recusou a operação de armazenamento")

    @staticmethod
    def _parse_generation(result: subprocess.CompletedProcess[bytes]) -> str:
        try:
            metadata = json.loads(result.stdout.decode("utf-8"))
            generation = metadata["generation"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise StorageError("metadados GCS sem geração válida") from exc
        if isinstance(generation, bool) or not isinstance(generation, (str, int)):
            raise StorageError("metadados GCS sem geração válida")
        return str(generation)

    @staticmethod
    def _parse_object(raw: bytes) -> dict[str, Any]:
        try:
            value = json.loads(
                raw.decode("utf-8"),
                parse_constant=_reject_non_finite_json_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise StorageError("auth.json não é JSON válido") from exc
        if not isinstance(value, dict):
            raise StorageError("auth.json não é um objeto JSON")
        return value


def _gcloud_environment() -> dict[str, str]:
    """Retorna o ambiente mínimo, preservando resolução do executável/config."""
    environment = {"PATH": os.environ.get("PATH", "")}
    for key in _GCLOUD_ENV_KEYS[1:]:
        if key in os.environ:
            environment[key] = os.environ[key]
    return environment


def _safe_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")[:500]


def _reject_non_finite_json_constant(_constant: str) -> None:
    raise ValueError("constante JSON não finita")


def _looks_missing(raw: bytes) -> bool:
    text = _safe_text(raw).lower()
    return "not found" in text or "404" in text or "does not exist" in text
