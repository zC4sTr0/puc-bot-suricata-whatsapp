# Troubleshooting

Não publique token Canvas, QR, sessão, JID, log de produção ou configuração real.

## Demo ou shadow falha

```bash
python -m compileall -q suricata
python -m suricata --mode shadow
python -m suricata --mode demo
```

Use Python 3.11 ou superior. A demo é offline e não prova acesso a serviços externos.

## A rodada recusa a configuração

Confira:

- `SURICATA_CANVAS_TOKEN` no ambiente autorizado;
- `SURICATA_ESTADO_URI` apontando para estado local descartável ou namespace GCS correto;
- `SURICATA_LEASE_MINUTOS` como inteiro positivo;
- destinos JSON válidos e JIDs de grupo;
- `SURICATA_ENTREGA=desligada` durante testes;
- sessão WhatsApp fora do clone.

Não apague estado nem troque bucket para contornar uma falha.

## A ponte WhatsApp não instala

```bash
cd suricata/whatsapp
npm ci --ignore-scripts
node --test
```

Use o lockfile. Pareamento é local e interativo; nunca ocorre em CI ou Cloud Run.

## A mensagem não foi enviada

Verifique, nesta ordem:

1. a fonte oficial no Canvas;
2. se a coleta foi completa;
3. janela BRT e corte das 21:00;
4. estado, lease e outbox;
5. autorização de entrega;
6. confirmação técnica do WhatsApp.

Ausência de mensagem não prova ausência de atividade.

## Cloud

Não altere produção por tentativa. Pare, preserve o estado e consulte [`deploy-gcp.md`](deploy-gcp.md). Mudanças de Job, Scheduler, IAM, Secret Manager, GCS ou imagem exigem autorização e read-back.

Para reportar um problema, use fixture sintética, commit e saída sanitizada. Vulnerabilidades devem seguir [`../SECURITY.md`](../SECURITY.md).
