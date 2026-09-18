"""Geração pura de identificadores determinísticos para mensagens Suricata."""

from hashlib import sha256


def message_id(grupo: str, event_id: str) -> str:
    """Retorna o identificador determinístico de um evento e seu grupo.

    Os argumentos são usados somente para calcular o digest; nenhum dado é
    armazenado, emitido ou registrado pela função.
    """
    if not isinstance(grupo, str) or not isinstance(event_id, str):
        raise TypeError("grupo e event_id devem ser strings")
    if not grupo or not event_id:
        raise ValueError("grupo e event_id não podem ser vazios")

    payload = f"{grupo}\0{event_id}".encode()
    digest = sha256(payload).hexdigest()[:18].upper()
    return f"3EB0{digest}"
