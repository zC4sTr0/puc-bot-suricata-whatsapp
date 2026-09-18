"""Compatibility facade for the canonical :mod:`suricata.config` module."""
from __future__ import annotations

from .config import Destino, _JID_GRUPO, destinos_do_ambiente

__all__ = ["Destino", "destinos_do_ambiente"]
