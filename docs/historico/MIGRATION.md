# Migração
> **Histórico — snapshot não normativo.** Preserva decisões e claims de época; não contém identificadores operacionais nem comandos copiáveis.


Origem: `<origem-historica-nao-versionada>`, extraída por allowlist controlada, preservando o layout conhecido para não misturar refatoração com separação.

A extração não copia `academico/`, `periodos/`, `.canvas/`, `scripts/academico/`, estado pessoal, capturas, sessão WhatsApp ou segredos. O runtime Python e os contratos Node foram mantidos; o Dockerfile da raiz foi adaptado para construir a partir do clone independente.

Limitações: o novo `AGENTS.md` ainda depende de aprovação do mecanismo de proteção de arquivos de instrução; o publicador de agenda precisa ser validado como comando exclusivamente Suricata antes do aceite final; build Docker real depende de daemon disponível; ações de produção exigem read-back e gates próprios.
