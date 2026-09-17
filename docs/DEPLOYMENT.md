# Deployment

## Local

```bash
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
python -m suricata --mode shadow
```

## Cloud

Use projeto, região, Artifact Registry, service account, bucket, Job e Scheduler próprios da Suricata. Faça build do clone limpo, registre commit e digest, e confira a imagem sem dados acadêmicos, auth, QR ou banco.

## Canário e corte

Canário usa estado separado, `SURICATA_ENTREGA=desligada`, nenhum destino real e `maxRetries=0`. Após read-back e autorização, o Job de produção aponta para o digest; o Scheduler único permanece habilitado. Nunca deixe caminho antigo e novo ativos ao mesmo tempo.

## Rollback

Aponte o Job para o digest anterior conhecido, faça read-back de imagem/args/env/retries/timeout, preserve o estado e observe a próxima execução. Não reescreva histórico e não apague objetos para “limpar”.
