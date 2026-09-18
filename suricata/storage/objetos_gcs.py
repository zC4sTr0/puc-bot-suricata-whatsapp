"""Operações CAS sobre um bucket GCS, com prefixo opcional (ex.: sombra).

Substitui, no caminho de produção, a CLI ``gcloud`` (ausente na imagem) por
Cloud Storage JSON API com ``ifGenerationMatch``. Toda leitura busca o
conteúdo **da geração anunciada** (``generation=``), então não existe leitura
rasgada entre metadados e corpo. HTTP 412 vira ``CASConflict``. Nenhum erro
inclui corpo, token ou conteúdo de objeto.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ._comum import Objeto
from .cas import CASConflict, StorageError
from .token import TokenGCP


class ObjetosGCS:
    """Operações CAS sobre um bucket, com prefixo opcional (ex.: sombra)."""

    MAX_TENTATIVAS_LEITURA = 3

    def __init__(self, uri: str, *, token: Callable[[], str] | None = None,
                 abrir: Callable[..., Any] = urllib.request.urlopen, timeout: float = 20.0) -> None:
        if not uri.startswith("gs://") or len(uri) <= 5:
            raise ValueError("URI de estado deve ser gs://bucket[/prefixo]")
        bucket, _, prefixo = uri[5:].partition("/")
        self.bucket = bucket
        self.prefixo = prefixo.strip("/")
        self._token = token or TokenGCP()
        self._abrir = abrir
        self.timeout = timeout

    def __repr__(self) -> str:
        return f"ObjetosGCS(bucket={self.bucket!r}, prefixo={self.prefixo!r})"

    def _nome(self, nome: str) -> str:
        if not nome or nome.startswith("/") or ".." in nome.split("/"):
            raise ValueError("nome de objeto inválido")
        return f"{self.prefixo}/{nome}" if self.prefixo else nome

    def _pedido(self, url: str, *, metodo: str = "GET", dados: bytes | None = None,
                tipo: str | None = None) -> tuple[int, bytes]:
        cabecalhos = {"Authorization": "Bearer " + self._token()}
        if tipo:
            cabecalhos["Content-Type"] = tipo
        pedido = urllib.request.Request(url, data=dados, method=metodo, headers=cabecalhos)
        for tentativa in range(3):
            try:
                with self._abrir(pedido, timeout=self.timeout) as resposta:
                    return int(resposta.status), resposta.read()
            except urllib.error.HTTPError as erro:
                if metodo != "POST" and erro.code >= 500 and tentativa < 2:
                    time.sleep(0.5 * (tentativa + 1))
                    continue
                return int(erro.code), b""
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if metodo != "POST" and tentativa < 2:
                    time.sleep(0.5 * (tentativa + 1))
                    continue
                raise StorageError("GCS inacessível") from exc
        raise StorageError("GCS inacessível")

    def _url_objeto(self, nome: str) -> str:
        return ("https://storage.googleapis.com/storage/v1/b/" + urllib.parse.quote(self.bucket, safe="")
                + "/o/" + urllib.parse.quote(self._nome(nome), safe=""))

    def ler(self, nome: str) -> Objeto:
        for _ in range(self.MAX_TENTATIVAS_LEITURA):
            status, corpo = self._pedido(self._url_objeto(nome))
            if status == 404:
                return Objeto(None, None)
            if status != 200:
                raise StorageError(f"GCS metadados HTTP {status}")
            try:
                meta = json.loads(corpo)
                generation = str(meta["generation"])
            except (KeyError, TypeError, ValueError) as exc:
                raise StorageError("metadados GCS sem geração") from exc
            status, dados = self._pedido(
                self._url_objeto(nome) + "?alt=media&generation=" + urllib.parse.quote(generation)
            )
            if status == 404:  # geração substituída entre as duas chamadas: releia
                continue
            if status != 200:
                raise StorageError(f"GCS leitura HTTP {status}")
            return Objeto(dados, generation, meta.get("updated"))
        raise StorageError("GCS geração anunciada indisponível após tentativas limitadas")

    def gravar(self, nome: str, dados: bytes, *, generation: str | None,
               tipo: str = "application/json") -> str:
        """``generation=None`` exige que o objeto não exista (ifGenerationMatch=0)."""
        url = ("https://storage.googleapis.com/upload/storage/v1/b/" + urllib.parse.quote(self.bucket, safe="")
               + "/o?uploadType=media&name=" + urllib.parse.quote(self._nome(nome), safe="")
               + "&ifGenerationMatch=" + urllib.parse.quote(generation or "0"))
        status, corpo = self._pedido(url, metodo="POST", dados=dados, tipo=tipo)
        if status == 412:
            raise CASConflict(f"conflito de geração em {nome}")
        if status not in (200, 201):
            raise StorageError(f"GCS gravação HTTP {status}")
        try:
            return str(json.loads(corpo)["generation"])
        except (KeyError, TypeError, ValueError) as exc:
            raise StorageError("gravação GCS sem geração") from exc

    def apagar(self, nome: str, *, generation: str) -> bool:
        status, _ = self._pedido(self._url_objeto(nome) + "?ifGenerationMatch=" + urllib.parse.quote(generation),
                                 metodo="DELETE")
        if status in (200, 204):
            return True
        if status in (404, 412):
            return False
        raise StorageError(f"GCS remoção HTTP {status}")
