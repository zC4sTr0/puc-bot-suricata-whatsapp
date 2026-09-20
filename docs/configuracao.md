# Configuração

Os nomes das variáveis são públicos; os valores não. Tokens, sessões, JIDs, buckets e caminhos reais ficam fora do Git.

## Variáveis principais

| Variável | Uso |
|---|---|
| `SURICATA_CANVAS_TOKEN` | token de leitura do Canvas; obrigatório em `rodada` |
| `SURICATA_ESTADO_URI` | diretório local ou namespace GCS para memória, lease e outbox |
| `SURICATA_ENTREGA` | somente `ligada` permite chamar WhatsApp; padrão seguro: desligada |
| `SURICATA_GRUPO_JID` | destino único, compatibilidade |
| `SURICATA_DESTINOS_JSON` | lista de destinos autorizados |
| `SURICATA_CONFIG` | arquivo externo opcional com configuração de destinos |
| `SURICATA_LEASE_MINUTOS` | duração do lease; padrão efetivo: `6` |
| `SURICATA_CURSOS_EXCLUIDOS` | IDs Canvas separados por vírgula |
| `SURICATA_WA_SESSION_OBJECT` | objeto externo da sessão WhatsApp, quando necessário |
| `SURICATA_WA_AUTH_DIR` | diretório externo da sessão para comandos Node |

Variáveis de teste como `SURICATA_STUB_SCENARIO`, `SURICATA_GCLOUD_BIN` e `SURICATA_WHATSAPP_LOCAL` não devem ser usadas como configuração de produção.

## Regras

- Entrega desligada é o padrão.
- `rodada` exige token e estado.
- Destinos precisam ser JSON válido, sem duplicatas e com JID de grupo válido.
- Lease inválido, namespace de sessão divergente ou configuração ambígua falham fechados.
- Sessão WhatsApp deve estar fora do clone e da imagem.
- O estado de canário deve ser separado do estado produtivo.

## Smoke test local

```bash
SURICATA_ESTADO_URI=./tmp-estado \
SURICATA_CANVAS_TOKEN=falso \
SURICATA_ENTREGA=desligada \
python -m suricata --mode rodada
```

Para o caminho mínimo:

```bash
python -m suricata --mode shadow
```

## Node

```bash
cd suricata/whatsapp
npm ci
node --test
```

## Produção

Em produção, injete o token pelo Secret Manager, use namespace GCS confirmado, mantenha sessão fora da imagem e faça read-back de imagem por digest, args, identidade, timeout, retries e URI de estado. Nunca publique valores reais, `.env`, `auth.json`, QR, JID ou logs com payload.
