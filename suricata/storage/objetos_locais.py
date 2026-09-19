"""Mesmo contrato de ``ObjetosGCS`` em diretório local (testes e sombra no PC).

Escrita com arquivo temporário + ``os.replace`` e metadados de geração em
arquivo ``.gen`` irmão; travas por objeto combinam um lock em memória
(registro por raiz+nome) com ``lock_arquivo`` em ``.locks/`` para proteger
processos distintos.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from ._comum import Objeto
from .cas import CASConflict, StorageError
from .locking import LockError, lock_arquivo

_TRAVAS_LOCAIS: dict[str, threading.Lock] = {}
_REGISTRO_TRAVAS_LOCAIS = threading.Lock()


def _trava_local(raiz: Path, nome: str) -> threading.Lock:
    chave = os.path.normcase(str(raiz.resolve(strict=False))) + "\0" + nome
    with _REGISTRO_TRAVAS_LOCAIS:
        return _TRAVAS_LOCAIS.setdefault(chave, threading.Lock())


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
                for _destino, conteudo in ((caminho, dados), (meta_caminho, metadados)):
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
