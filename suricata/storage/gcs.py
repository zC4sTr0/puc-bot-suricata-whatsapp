"""Objetos versionados (CAS) para estado, outbox, lease e sessão do Suricata.

Substitui, no caminho de produção, a CLI ``gcloud`` (ausente na imagem) por
Cloud Storage JSON API com ``ifGenerationMatch``. No Cloud Run o token vem do
metadata server; fora dele, de ``gcloud auth print-access-token`` (só uso local).

Toda leitura busca o conteúdo **da geração anunciada** (``generation=``), então
não existe leitura rasgada entre metadados e corpo. HTTP 412 vira
``CASConflict``. Nenhum erro inclui corpo, token ou conteúdo de objeto.
"""
from __future__ import annotations

import json
import hashlib
import os
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from .cas import AuthSnapshot, CASConflict, ReadBackError, StorageError
from .locking import LockError, lock_arquivo

METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"

_TRAVAS_LOCAIS: dict[str, threading.Lock] = {}
_REGISTRO_TRAVAS_LOCAIS = threading.Lock()


def _trava_local(raiz: Path, nome: str) -> threading.Lock:
    chave = os.path.normcase(str(raiz.resolve(strict=False))) + "\0" + nome
    with _REGISTRO_TRAVAS_LOCAIS:
        return _TRAVAS_LOCAIS.setdefault(chave, threading.Lock())


@dataclass(frozen=True)
class Objeto:
    dados: bytes | None
    generation: str | None
    atualizado_em: str | None = None


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
        except Exception as exc:  # noqa: BLE001 - erro sanitizado
            raise StorageError("metadata server indisponível para token GCS") from exc
        return str(carga["access_token"]).strip(), float(carga.get("expires_in", 300))

    @staticmethod
    def _gcloud_local() -> tuple[str, float]:
        gcloud = os.environ.get("SURICATA_GCLOUD_BIN", "gcloud")
        try:
            saida = subprocess.run([gcloud, "auth", "print-access-token"], capture_output=True,
                                   timeout=60, check=True, shell=os.name == "nt")
        except Exception as exc:  # noqa: BLE001
            raise StorageError("token GCS local indisponível") from exc
        return saida.stdout.decode().strip(), 1800.0


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


class ObjetosLocais:
    """Mesmo contrato de ``ObjetosGCS`` em diretório local (testes e sombra no PC)."""

    def __init__(self, raiz: str | Path) -> None:
        self.raiz = Path(raiz)

    def _caminho(self, nome: str) -> Path:
        if not nome or nome.startswith("/") or ".." in nome.split("/"):
            raise ValueError("nome de objeto inválido")
        return self.raiz / nome

    def _lock_path(self, nome: str) -> Path:
        chave = os.path.normcase(str(self.raiz.resolve(strict=False))) + "\0" + nome
        digest = hashlib.sha256(chave.encode("utf-8")).hexdigest()
        return self.raiz / ".locks" / f"{digest}.lock"

    @contextmanager
    def _trava_objeto(self, nome: str):
        with _trava_local(self.raiz, nome):
            try:
                with lock_arquivo(
                    self._lock_path(nome), timeout=30.0, namespace="SuricataStorage",
                    recurso="armazenamento local",
                ):
                    yield
            except LockError as exc:
                raise StorageError(str(exc)) from exc

    def ler(self, nome: str) -> Objeto:
        caminho = self._caminho(nome)
        with self._trava_objeto(nome):
            if not caminho.exists():
                return Objeto(None, None)
            meta = json.loads(caminho.with_name(caminho.name + ".gen").read_text())
            return Objeto(caminho.read_bytes(), str(meta["generation"]), meta.get("updated"))

    def gravar(self, nome: str, dados: bytes, *, generation: str | None, tipo: str = "application/json") -> str:
        caminho = self._caminho(nome)
        meta_caminho = caminho.with_name(caminho.name + ".gen")
        with self._trava_objeto(nome):
            atual = None
            if caminho.exists():
                atual = str(json.loads(meta_caminho.read_text())["generation"])
            if atual != generation:
                raise CASConflict(f"conflito de geração em {nome}")
            nova = str(int(atual or "0") + 1)
            caminho.parent.mkdir(parents=True, exist_ok=True)
            from datetime import datetime, timezone
            metadados = json.dumps(
                {"generation": nova, "updated": datetime.now(timezone.utc).isoformat()}
            ).encode()

            temporarios: list[Path | None] = []
            backups: list[tuple[Path, Path]] = []
            trocados: list[Path] = []
            try:
                for destino, conteudo in ((caminho, dados), (meta_caminho, metadados)):
                    with tempfile.NamedTemporaryFile(
                        mode="wb", dir=caminho.parent, prefix=f".{caminho.name}.", suffix=".tmp", delete=False
                    ) as arquivo:
                        arquivo.write(conteudo)
                        arquivo.flush()
                        os.fsync(arquivo.fileno())
                        temporarios.append(Path(arquivo.name))

                for destino in (caminho, meta_caminho):
                    if destino.exists():
                        with tempfile.NamedTemporaryFile(
                            mode="wb", dir=caminho.parent, prefix=f".{destino.name}.", suffix=".bak", delete=False
                        ) as arquivo:
                            arquivo.write(destino.read_bytes())
                            arquivo.flush()
                            os.fsync(arquivo.fileno())
                            backups.append((destino, Path(arquivo.name)))

                os.replace(temporarios[0], caminho)
                temporarios[0] = None
                trocados.append(caminho)
                os.replace(temporarios[1], meta_caminho)
                temporarios[1] = None
                trocados.append(meta_caminho)
                return nova
            except Exception:
                destinos_com_backup = {destino for destino, _ in backups}
                for destino in trocados:
                    if destino not in destinos_com_backup and destino.exists():
                        destino.unlink()
                for destino, backup in backups:
                    if backup.exists():
                        os.replace(backup, destino)
                raise
            finally:
                for temporario in (*temporarios, *(backup for _, backup in backups)):
                    if temporario is not None and temporario.exists():
                        temporario.unlink()

    def apagar(self, nome: str, *, generation: str) -> bool:
        caminho = self._caminho(nome)
        with self._trava_objeto(nome):
            if not caminho.exists():
                return False
            atual = str(json.loads(caminho.with_name(caminho.name + ".gen").read_text())["generation"])
            if atual != generation:
                return False
            caminho.unlink()
            caminho.with_name(caminho.name + ".gen").unlink()
            return True


def construir_objetos(uri: str) -> ObjetosGCS | ObjetosLocais:
    return ObjetosGCS(uri) if uri.startswith("gs://") else ObjetosLocais(uri)


class SessaoWhatsApp:
    """``read_auth``/``write_auth`` (contrato de ``WhatsAppBridge``) sobre objetos CAS."""

    NOME = "whatsapp/auth.json"

    def __init__(self, objetos: ObjetosGCS | ObjetosLocais) -> None:
        self.objetos = objetos

    def read_auth(self) -> AuthSnapshot:
        obj = self.objetos.ler(self.NOME)
        if obj.dados is None:
            return AuthSnapshot(None, None)
        try:
            valor = json.loads(obj.dados.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise StorageError("auth.json não é JSON válido") from exc
        if not isinstance(valor, dict):
            raise StorageError("auth.json não é um objeto JSON")
        return AuthSnapshot(valor, obj.generation)

    def write_auth(self, value: dict[str, Any], *, expected_generation: str | None) -> AuthSnapshot:
        dados = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.objetos.gravar(self.NOME, dados, generation=expected_generation)
        depois = self.read_auth()
        if depois.value != value:
            raise ReadBackError("read-back da sessão WhatsApp não confirmou a escrita")
        return depois


__all__ = ["Objeto", "ObjetosGCS", "ObjetosLocais", "SessaoWhatsApp", "TokenGCP", "construir_objetos"]
