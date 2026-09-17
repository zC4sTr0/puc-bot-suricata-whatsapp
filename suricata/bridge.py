"""Ponte isolada Python -> Node para o transporte WhatsApp do Suricata."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from .message_id import message_id
from .storage.cas import AuthSnapshot, CASConflict, SuricataSessionStorage, StorageError


class BridgeError(RuntimeError):
    """Falha sanitizada na ponte, sem stdout/stderr externo."""


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


class WhatsAppBridge:
    def __init__(
        self,
        storage: SuricataSessionStorage,
        *,
        node: str = "node",
        script: str | Path | None = None,
        timeout: float = 150.0,
        run: Runner = subprocess.run,
    ) -> None:
        self.storage = storage
        self.node = node
        self.script = Path(script) if script else Path(__file__).with_name("whatsapp") / "enviar.mjs"
        self.timeout = timeout
        self._run = run

    def enviar_lote(self, grupo_jid: str, eventos: list[dict[str, str]]) -> dict[str, Any]:
        eventos_validados = self._validar_entrada(grupo_jid, eventos)
        snapshot = self.storage.read_auth()
        if snapshot.value is None:
            return {"sessao": "ausente", "resultados": []}

        with tempfile.TemporaryDirectory(prefix=".wa-auth-") as temp:
            auth_dir = Path(temp) / "auth"
            self._materializar(snapshot.value, auth_dir)
            payload = {
                "auth_dir": str(auth_dir),
                "grupo_jid": grupo_jid,
                "mensagens": [
                    {"event_id": e["event_id"], "message_id": e["message_id"], "texto": e["texto"]}
                    for e in eventos_validados
                ],
            }
            resultado = self._executar(payload)
            atualizado = self._ler_auth(auth_dir)
            if resultado.get("sessao") == "ok" and atualizado != snapshot.value:
                self.storage.write_auth(atualizado, expected_generation=snapshot.generation)
            return resultado

    @staticmethod
    def _validar_entrada(grupo_jid: object, eventos: object) -> list[dict[str, str]]:
        """Valida o contrato inteiro antes de tocar storage ou subprocesso."""
        if not WhatsAppBridge._texto_valido(grupo_jid):
            raise BridgeError("entrada inválida para o bridge")
        if not isinstance(eventos, list) or not eventos:
            raise BridgeError("eventos inválidos para o bridge")

        validados: list[dict[str, str]] = []
        event_ids: set[str] = set()
        for evento in eventos:
            if not isinstance(evento, Mapping):
                raise BridgeError("eventos inválidos para o bridge")
            event_id = evento.get("event_id")
            message = evento.get("message_id")
            texto = evento.get("texto")
            if not all(WhatsAppBridge._texto_valido(value) for value in (event_id, message)):
                raise BridgeError("eventos inválidos para o bridge")
            # Aviso tem várias linhas: \n é legítimo no texto; os demais controles não.
            if not WhatsAppBridge._texto_valido(texto, permitidos="\n"):
                raise BridgeError("eventos inválidos para o bridge")
            assert isinstance(event_id, str)
            assert isinstance(message, str)
            assert isinstance(texto, str)
            if event_id in event_ids:
                raise BridgeError("eventos inválidos para o bridge")
            event_ids.add(event_id)
            if message != message_id(grupo_jid, event_id):
                raise BridgeError("eventos inválidos para o bridge")
            validados.append({"event_id": event_id, "message_id": message, "texto": texto})
        return validados

    @staticmethod
    def _texto_valido(value: object, permitidos: str = "") -> bool:
        return (isinstance(value, str) and bool(value.strip())
                and not any(ord(char) < 32 and char not in permitidos for char in value))

    def _executar(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            # O contrato de enviar.mjs lê SURICATA_WA_AUTH_DIR, mas a ponte
            # fornece auth_dir pelo stdin; nenhum SURICATA_* é necessário no
            # processo filho. PATH é suficiente para localizar o runtime Node.
            environment = {"PATH": os.environ.get("PATH", "")}
            completed = self._run(
                [self.node, str(self.script)],
                input=(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(),
                capture_output=True,
                timeout=self.timeout,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            raise BridgeError("falha ou timeout no processo WhatsApp") from exc
        except OSError as exc:
            raise BridgeError("falha ao iniciar o processo WhatsApp") from exc
        linhas = [linha for linha in completed.stdout.decode("utf-8", errors="replace").splitlines() if linha.strip()]
        try:
            resultado = json.loads(linhas[-1])  # a última linha é o contrato; bibliotecas podem imprimir antes
        except (IndexError, json.JSONDecodeError) as exc:
            raise BridgeError(self._diagnostico("resposta inválida do processo WhatsApp", completed)) from exc
        if not isinstance(resultado, dict) or resultado.get("sessao") not in {"ok", "logged_out", "timeout", "erro"}:
            raise BridgeError(self._diagnostico("resposta sem estado de sessão válido", completed))
        entregue = resultado.get("sessao") == "ok" and self._sucesso_valido(payload, resultado)
        # ACK do servidor é a prova de entrega: um crash do Node DEPOIS dele (medido no Cloud Run)
        # não pode transformar envio confirmado em reenvio, nem impedir a gravação das credenciais.
        if completed.returncode != 0 and resultado.get("sessao") not in {"logged_out", "timeout"} and not entregue:
            raise BridgeError(self._diagnostico("processo WhatsApp falhou", completed, resultado))
        if resultado.get("sessao") == "ok" and not self._sucesso_valido(payload, resultado):
            raise BridgeError(self._diagnostico("resposta de sucesso inconsistente", completed, resultado))
        return resultado

    @staticmethod
    def _diagnostico(motivo: str, completed: Any, resultado: dict[str, Any] | None = None) -> str:
        """Motivo + código + detalhe do Node + fim do stderr, sem telefone, JID longo nem URL."""
        partes = [motivo, f"exit={completed.returncode}"]
        if resultado:
            itens = resultado.get("resultados") or []
            partes.append("detalhe=" + str(resultado.get("detalhe") or resultado.get("erro") or ""))
            if itens:
                partes.append("acks=" + ",".join(f"{i.get('ack')}/{i.get('status')}/{i.get('timeout')}/{i.get('erro')}"
                                                 for i in itens if isinstance(i, dict)))
        cauda = (completed.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()[-2:]
        if cauda:
            # stderr é texto livre: valores após "=" ou ":" com cara de credencial ficam de fora.
            linhas = [re.sub(r"(?i)(token|key|secret|cookie|auth|senha)\S*", "<omitido>", re.sub(r"=\S+", "=<omitido>", linha))
                      for linha in cauda]
            partes.append("stderr=" + " / ".join(linha[:150] for linha in linhas))
        texto = " | ".join(partes)
        texto = re.sub(r"https?://\S+", "<url>", texto)
        texto = re.sub(r"\d{6,}", "#", texto)
        return texto[:400]

    @staticmethod
    def _sucesso_valido(payload: dict[str, Any], resultado: dict[str, Any]) -> bool:
        """Aceita ``ok`` somente quando cada envio foi confirmado sem ambiguidade."""
        mensagens = payload.get("mensagens")
        recebidos = resultado.get("resultados")
        if not isinstance(mensagens, list) or not isinstance(recebidos, list):
            return False
        if len(recebidos) != len(mensagens):
            return False

        esperados: Counter[tuple[str, str]] = Counter()
        for mensagem in mensagens:
            if not isinstance(mensagem, dict):
                return False
            event_id = mensagem.get("event_id")
            message_id = mensagem.get("message_id")
            if not isinstance(event_id, str) or not isinstance(message_id, str):
                return False
            esperados[(event_id, message_id)] += 1

        encontrados: Counter[tuple[str, str]] = Counter()
        for item in recebidos:
            if not isinstance(item, dict):
                return False
            event_id = item.get("event_id")
            message_id = item.get("message_id")
            status = item.get("status")
            if not isinstance(event_id, str) or not isinstance(message_id, str):
                return False
            if item.get("ack") is not True or type(status) is not int or status < 2:
                return False
            encontrados[(event_id, message_id)] += 1
        return encontrados == esperados

    @staticmethod
    def _materializar(value: dict[str, Any], root: Path) -> None:
        root.mkdir(mode=0o700, parents=True)
        for name, content in value.items():
            if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
                raise StorageError("nome inválido na sessão WhatsApp")
            if not isinstance(content, str):
                raise StorageError("conteúdo inválido na sessão WhatsApp")
            target = root / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            os.chmod(target, 0o600)

    @staticmethod
    def _ler_auth(root: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in root.rglob("*"):
            if item.is_symlink() or not item.is_file():
                continue
            relative = item.relative_to(root)
            result[relative.as_posix()] = item.read_text(encoding="utf-8")
        return result


__all__ = ["WhatsAppBridge", "BridgeError"]
