"""Lock cross-processo portátil para o armazenamento do Suricata."""
from __future__ import annotations

import ctypes
import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockError(RuntimeError):
    """Falha sanitizada ao preparar ou adquirir um lock."""


def _retry_fs(operation, *, deadline: float, error: str):
    while True:
        try:
            return operation()
        except FileNotFoundError:
            raise
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise LockError(error) from exc
            time.sleep(min(0.01, max(0.001, deadline - time.monotonic())))


@contextmanager
def lock_arquivo(
    path: str | Path,
    *,
    timeout: float = 30.0,
    namespace: str = "SuricataStorage",
    recurso: str | None = None,
) -> Iterator[None]:
    """Adquire lock entre processos, com mutex kernel no Windows e ``fcntl`` no POSIX.

    O arquivo serve apenas como identidade estável no POSIX. No Windows a
    coordenação é feita exclusivamente pelo mutex nomeado do kernel; handles
    abandonados são recuperados pelo próximo adquirente.
    """
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout < 0:
        raise ValueError("timeout de lock inválido")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace de lock inválido")
    path = Path(path)
    deadline = time.monotonic() + timeout
    recurso = recurso or namespace.lower()
    preparo = f"não foi possível preparar o lock do {recurso}"
    aquisicao = f"não foi possível adquirir lock do {recurso}"
    timeout_msg = f"timeout ao adquirir lock do {recurso}"
    _retry_fs(lambda: path.parent.mkdir(parents=True, exist_ok=True), deadline=deadline, error=preparo)

    if os.name == "nt":
        name = f"Local\\{namespace}-" + hashlib.sha256(
            os.path.normcase(str(path.resolve(strict=False))).encode("utf-8")
        ).hexdigest()
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
            kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel32.WaitForSingleObject.restype = ctypes.c_uint32
            kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel32.CreateMutexW(None, 0, name)
        except Exception as exc:  # noqa: BLE001 - erro sanitizado
            raise LockError(f"não foi possível criar mutex do {recurso}") from exc
        if not handle:
            raise LockError(f"não foi possível criar mutex do {recurso}")
        try:
            milliseconds = min(0xFFFFFFFF, max(0, int(timeout * 1000)))
            result = kernel32.WaitForSingleObject(handle, milliseconds)
            if result not in (0, 0x80):  # WAIT_OBJECT_0 / WAIT_ABANDONED
                if result == 0x102:  # WAIT_TIMEOUT
                    raise LockError(timeout_msg)
                raise LockError(aquisicao)
            try:
                yield
            finally:
                kernel32.ReleaseMutex(handle)
        finally:
            kernel32.CloseHandle(handle)
        return

    import fcntl

    _retry_fs(lambda: path.touch(exist_ok=True), deadline=deadline, error=preparo)
    handle = _retry_fs(lambda: path.open("r+b"), deadline=deadline, error=aquisicao)
    with handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise LockError(timeout_msg) from exc
                time.sleep(min(0.01, max(0.001, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


__all__ = ["LockError", "lock_arquivo"]
