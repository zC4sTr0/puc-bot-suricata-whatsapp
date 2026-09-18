"""Facade de compatibilidade do armazenamento CAS (decomposição de ``gcs.py``).

Este módulo historicamente concentrou quatro responsabilidades, que agora
vivem em módulos próprios:

- ``suricata.storage.token`` — ``TokenGCP`` (token OAuth com cache) e a
  constante ``METADATA_TOKEN_URL``;
- ``suricata.storage.objetos_gcs`` — ``ObjetosGCS`` (CAS via Cloud Storage
  JSON API com ``ifGenerationMatch``; leitura sempre da geração anunciada,
  sem leitura rasgada; HTTP 412 vira ``CASConflict``; erros sanitizados);
- ``suricata.storage.objetos_locais`` — ``ObjetosLocais`` (mesmo contrato em
  diretório local, com travas por objeto e escrita atômica);
- ``suricata.storage.sessao`` — ``SessaoWhatsApp`` (``read_auth``/``write_auth``
  sobre objetos CAS);
- ``suricata.storage._comum`` — ``Objeto`` (tipo de valor compartilhado pelos
  backends, para que nenhum dependa do outro).

Os re-exports abaixo preservam a **identidade** dos símbolos: importar
``X`` daqui continua devolvendo exatamente o objeto dos módulos novos.

``construir_objetos`` permanece **neste módulo** porque a fábrica precisa dos
dois backends (GCS e local): o pacote ``suricata.storage`` não tem
``__init__.py`` (é pacote de namespace implícito), e alocá-la em qualquer
módulo novo obrigaria um backend a importar o irmão — este módulo é a única
raiz de composição que já referencia ambos sem criar acoplamento cruzado.
"""
from __future__ import annotations

import os  # noqa: F401 - ponto de patch histórico: testes fazem
# ``patch("suricata.storage.gcs.os.replace")``, que resolve para o módulo
# ``os`` global (o mesmo usado por ``objetos_locais`` em tempo de chamada).

# Tipos e erros reexportados para preservar a superfície histórica do módulo
# (eram atributos de ``gcs`` via import, antes da decomposição).
from .cas import AuthSnapshot, CASConflict, ReadBackError, StorageError
from .locking import LockError, lock_arquivo  # noqa: F401 - reexport de compatibilidade

from ._comum import Objeto
from .objetos_gcs import ObjetosGCS
from .objetos_locais import ObjetosLocais
from .sessao import SessaoWhatsApp
from .token import METADATA_TOKEN_URL, TokenGCP


def construir_objetos(uri: str) -> ObjetosGCS | ObjetosLocais:
    """Fábrica de backend por URI: ``gs://`` vira GCS, resto vira local."""
    return ObjetosGCS(uri) if uri.startswith("gs://") else ObjetosLocais(uri)


__all__ = ["Objeto", "ObjetosGCS", "ObjetosLocais", "SessaoWhatsApp", "TokenGCP", "construir_objetos"]
