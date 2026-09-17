# Configuração

## Variáveis

- `SURICATA_CANVAS_TOKEN`: Secret Manager; nunca em argv/arquivo.
- `SURICATA_ESTADO_URI`: bucket/prefixo Suricata ou diretório temporário de teste.
- `SURICATA_ENTREGA`: use `desligada` em testes/canário; `ligada` somente no corte autorizado.
- `SURICATA_GRUPO_JID` e `SURICATA_DESTINOS_JSON`: ambiente autorizado; nunca versionar valores reais.
- `SURICATA_LEASE_MINUTOS`: lease da rodada, com validação fail-closed.
- `SURICATA_WA_AUTH_DIR`: diretório externo temporário da sessão; nunca dentro do clone.

## Regras

O arquivo `suricata/config.example.json` é somente exemplo do modo `sentinela`. Segredos vêm do ambiente. Recursos GCP devem usar o namespace Suricata e permissões mínimas. Antes de uma alteração, faça read-back do recurso exato.
