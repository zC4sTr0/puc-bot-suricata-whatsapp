# Deploy no Google Cloud

Este é um procedimento público e sanitizado. Preencha os valores somente no ambiente autorizado. Nunca coloque projeto, bucket, Job, Scheduler, conta de serviço, digest ou segredo real neste arquivo.

## Fluxo

```text
commit limpo → Cloud Build → Artifact Registry → canário sem entrega → Job produtivo
```

O Job recebe uma imagem por **digest**, nunca por tag móvel. O Scheduler apenas dispara o Job; ele não autoriza entrega.

## Antes do build

Confirme:

```bash
git rev-parse HEAD
git status --short
python -m compileall -q suricata
python -m pytest -q
python -m suricata --mode shadow
```

Use um checkout limpo. Não inclua token, sessão, QR, banco, log ou `.env` preenchido no contexto.

## Build

O build remoto pode ser feito sem Docker local:

```bash
gcloud builds submit . \
  --project="<projeto-confirmado>" \
  --tag="<registry-confirmado>/suricata:<commit-curto>"
```

Leia de volta o build e o digest completo no Artifact Registry. Sem digest confirmado, não atualize nenhum Job.

## Canário

Atualize somente o Job canário para o digest confirmado. O canário deve ter:

- estado separado;
- `SURICATA_ENTREGA=desligada`;
- nenhum destino real;
- `--mode rodada`;
- retries e timeout limitados;
- identidade autorizada apenas para o que o canário precisa.

Execute, leia o status e inspecione logs sanitizados. `SUCCEEDED` prova execução do container; não prova entrega WhatsApp.

## Produção

Antes do corte, registre o digest anterior para rollback e confirme que não há execução concorrente.

Altere somente a imagem do Job produtivo. Não altere Scheduler, frequência, IAM, secrets, bucket, sessão, estado, timeout ou retries no mesmo corte.

Depois do update, faça read-back de:

- digest e geração;
- args e variáveis não secretas;
- identidade e referências de secrets;
- timeout, retries e namespace de estado;
- Scheduler único e sua agenda.

Observe uma execução completa. Entrega só é considerada confirmada com identidade de evento, `message_id`, ACK válido e cardinalidade correta.

## Rollback

Volte ao digest anterior conhecido. Não reconstrua a imagem, não use `latest` e não apague estado, lease, outbox ou histórico. Leia novamente a configuração antes de reabrir a entrega.

## Regras

- Toda mutação exige autorização explícita e read-back.
- Nunca crie um segundo Scheduler.
- Nunca ligue entrega no canário.
- Nunca coloque segredos em argv, Dockerfile, imagem ou logs.
- Se a configuração, execução ou ACK divergir, pare e preserve as evidências.
