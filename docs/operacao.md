# Operação

Este é o único documento técnico necessário depois do [guia rápido](guia.md).

## Configuração mínima

| Variável | Função |
|---|---|
| `SURICATA_CANVAS_TOKEN` | leitura do Canvas em `rodada` |
| `SURICATA_ESTADO_URI` | estado local ou namespace GCS |
| `SURICATA_ENTREGA` | somente `ligada` permite envio |
| `SURICATA_GRUPO_JID` | destino único, compatibilidade |
| `SURICATA_DESTINOS_JSON` | lista de destinos |
| `SURICATA_LEASE_MINUTOS` | lease; padrão `6` |
| `SURICATA_WA_AUTH_DIR` | sessão Node fora do repositório |

Segredos, sessão, QR, JIDs, buckets e valores reais ficam fora do Git.

## Teste local

```bash
python -m suricata --mode shadow
python -m suricata --mode demo

SURICATA_ESTADO_URI=./tmp-estado \
SURICATA_CANVAS_TOKEN=falso \
SURICATA_ENTREGA=desligada \
python -m suricata --mode rodada
```

Use estado descartável. A entrega deve permanecer desligada.

## Como funciona

1. Python consulta o Canvas.
2. O planejador escolhe novidades e horário.
3. Lease, CAS e outbox protegem o estado.
4. Node conversa com o WhatsApp.
5. Só ACK válido marca o item como enviado.

O relógio é `America/Sao_Paulo`: 07:00 reabre, 12:00 permite aviso extra, 18:00 prepara o lembrete e 21:00 fecha o envio.

## Operação real

Antes de ligar a entrega, confirme:

- autorização do destino;
- token do Canvas no ambiente autorizado;
- estado protegido e separado do canário;
- sessão WhatsApp fora do clone;
- destino correto;
- janela aberta;
- ACK disponível.

Qualquer configuração ausente, ambígua ou inválida deve falhar fechada.

## Deploy

O fluxo é:

```text
commit limpo → Cloud Build → imagem por digest → canário sem entrega → produção
```

Antes do build:

```bash
git status --short
python -m compileall -q suricata
python -m pytest -q
```

No canário, mantenha estado separado, `SURICATA_ENTREGA=desligada`, nenhum destino real e retries limitados. Em produção, altere somente a imagem do Job. Não mude Scheduler, IAM, secrets, bucket, sessão ou estado no mesmo corte.

Leia de volta digest, geração, args, identidade, timeout, retries, estado e Scheduler. Guarde o digest anterior para rollback.

## Se algo falhar

Não apague estado, lease ou outbox. Preserve logs sanitizados, confirme a fonte no Canvas e verifique horário, coleta, configuração, estado, sessão e ACK.

Rollback é voltar ao digest anterior conhecido. Nunca reconstrua a imagem nem use `latest`.

Para um problema no projeto, abra uma issue com fixture fictícia, commit e saída sanitizada. Vulnerabilidades seguem [`../SECURITY.md`](../SECURITY.md).
