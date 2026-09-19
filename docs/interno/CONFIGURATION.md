# Configuração

## Variáveis

- `SURICATA_CANVAS_TOKEN`: Secret Manager; nunca em argv/arquivo.
- `SURICATA_ESTADO_URI`: bucket/prefixo Suricata ou diretório temporário de teste.
- `SURICATA_ENTREGA`: use `desligada` em testes/canário; `ligada` somente no corte autorizado.
- `SURICATA_GRUPO_JID` e `SURICATA_DESTINOS_JSON`: ambiente autorizado; nunca versionar valores reais.
- `SURICATA_LEASE_MINUTOS`: lease da rodada, com validação fail-closed.
- `SURICATA_WA_SESSION_OBJECT`: URI opcional do objeto de sessão GCS; quando presente, deve estar no mesmo bucket/prefixo de `SURICATA_ESTADO_URI`, ou a inicialização falha fechada. Quando ausente, usa `whatsapp/auth.json` dentro do namespace de estado.
- `SURICATA_WA_AUTH_DIR`: diretório externo temporário da sessão local; nunca dentro do clone.

## Regras

Toda configuração funcional vem do ambiente do processo ou do Secret Manager; não existe arquivo de configuração de modo (o `config.example.json` do modo `sentinela` foi removido na simplificação de 2026-09-18, junto com o próprio modo). Recursos GCP devem usar o namespace Suricata e permissões mínimas. Antes de uma alteração, faça read-back do recurso exato.
