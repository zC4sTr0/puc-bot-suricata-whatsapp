"""``read_auth``/``write_auth`` (contrato de ``WhatsAppBridge``) sobre objetos CAS.

Funciona sobre qualquer backend que exponha ``ler``/``gravar`` com o contrato
de geração (``ObjetosGCS`` ou ``ObjetosLocais``); por isso não importa nenhum
backend concreto — a união nos hints é apenas documentação de tipos.
"""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from .cas import AuthSnapshot, ReadBackError, StorageError

if TYPE_CHECKING:  # evita acoplar sessão aos backends concretos
    from .objetos_gcs import ObjetosGCS
    from .objetos_locais import ObjetosLocais


class SessaoWhatsApp:
    """``read_auth``/``write_auth`` sobre um objeto no namespace de estado."""

    NOME = "whatsapp/auth.json"

    def __init__(self, objetos: ObjetosGCS | ObjetosLocais, nome: str | None = None) -> None:
        self.objetos = objetos
        self.nome = _nome_sessao(objetos, nome)

    def read_auth(self) -> AuthSnapshot:
        obj = self.objetos.ler(self.nome)
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
        self.objetos.gravar(self.nome, dados, generation=expected_generation)
        depois = self.read_auth()
        if depois.value != value:
            raise ReadBackError("read-back da sessão WhatsApp não confirmou a escrita")
        return depois


def _nome_sessao(objetos: Any, nome: str | None) -> str:
    """Resolve uma sessão relativa ao namespace de estado, sem fallback cross-product."""
    configurado = nome or os.environ.get("SURICATA_WA_SESSION_OBJECT")
    if not configurado:
        return SessaoWhatsApp.NOME
    if not isinstance(configurado, str) or not configurado.startswith("gs://"):
        raise StorageError("objeto da sessão WhatsApp inválido")
    if not hasattr(objetos, "bucket"):
        raise StorageError("objeto da sessão GCS exige backend GCS")
    bucket, _, caminho = configurado[5:].partition("/")
    prefixo = getattr(objetos, "prefixo", "").strip("/")
    esperado = f"{prefixo}/{SessaoWhatsApp.NOME}" if prefixo else SessaoWhatsApp.NOME
    if bucket != objetos.bucket or caminho != esperado:
        raise StorageError("objeto da sessão WhatsApp fora do namespace de estado")
    return SessaoWhatsApp.NOME
