"""Permite executar o Suricata com ``python -m suricata``."""
from .entrypoint import main

if __name__ == "__main__":
    raise SystemExit(main())
