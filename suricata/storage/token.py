"""Token OAuth GCP com cache; o valor nunca aparece em repr, erro ou log.

No Cloud Run o token vem do metadata server (``METADATA_TOKEN_URL``); fora
dele, de ``gcloud auth print-access-token`` (somente uso local).
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
from collections.abc import Callable

from .cas import StorageError

METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"


def _em_cloud_run() -> bool:
    return bool(os.environ.get("CLOUD_RUN_JOB") or os.environ.get("K_SERVICE"))


class TokenGCP:
    """Token OAuth com cache; nunca aparece em repr, erro ou log."""

    def __init__(self, fonte: Callable[[], tuple[str, float]] | None = None) -> None:
        self._fonte = fonte or (self._metadata if _em_cloud_run() else self._gcloud_local)
        self._valor: str | None = None
        self._expira = 0.0
        self._trava = threading.Lock()

    def __repr__(self) -> str:
        return "TokenGCP(***)"

    def __call__(self) -> str:
        with self._trava:
            if self._valor is None or time.monotonic() > self._expira - 60:
                self._valor, validade = self._fonte()
                self._expira = time.monotonic() + validade
            return self._valor

    @staticmethod
    def _metadata() -> tuple[str, float]:
        pedido = urllib.request.Request(METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"})
        try:
            with urllib.request.urlopen(pedido, timeout=5) as resposta:
                carga = json.load(resposta)
        except Exception as exc:  # erro sanitizado: nada do token vaza
            raise StorageError("metadata server indisponível para token GCS") from exc
        return str(carga["access_token"]).strip(), float(carga.get("expires_in", 300))

    @staticmethod
    def _gcloud_local() -> tuple[str, float]:
        gcloud = os.environ.get("SURICATA_GCLOUD_BIN", "gcloud")
        try:
            saida = subprocess.run([gcloud, "auth", "print-access-token"], capture_output=True,
                                   timeout=60, check=True, shell=os.name == "nt")
        except Exception as exc:
            raise StorageError("token GCS local indisponível") from exc
        return saida.stdout.decode().strip(), 1800.0
