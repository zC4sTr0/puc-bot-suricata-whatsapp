# Troubleshooting público

Este guia cobre problemas locais e de primeira configuração. Não peça nem
publique token Canvas, QR code, sessão WhatsApp, JID real, log de produção ou
configuração de cloud.

## O demo não inicia

Confirme Python 3.11+ e execute:

```bash
python -m compileall -q suricata
python -m suricata --mode demo
```

O demo usa fixtures sintéticas, relógio controlado e entrega desligada. Ele não
prova acesso ao Canvas, GCP ou WhatsApp.

## O modo `shadow` falha

Execute:

```bash
python -m suricata --mode shadow
```

O resultado esperado é JSON com `mode=shadow`, `status=ok`, `adapter=none` e
código de saída zero. Esse modo não consulta rede, não grava estado persistente
e não chama Node.

## A rodada recusa a configuração

Leia [`configuracao.md`](configuracao.md) e confira, sem colar valores reais em
issues:

- `SURICATA_CANVAS_TOKEN` está disponível somente no ambiente autorizado;
- `SURICATA_ESTADO_URI` aponta para um diretório local descartável ou namespace
  GCS confirmado;
- `SURICATA_LEASE_MINUTOS` é inteiro positivo;
- destinos JSON são válidos e os JIDs têm formato de grupo;
- `SURICATA_ENTREGA` permanece `desligada` durante testes;
- sessões WhatsApp ficam fora do clone.

Não corrija uma falha removendo o estado ou trocando o bucket sem entender a
causa. Configuração ambígua deve falhar fechada.

## A ponte WhatsApp não instala

A ponte Node vive em [`../suricata/whatsapp/README.md`](../suricata/whatsapp/README.md).
Use o lockfile versionado:

```bash
cd suricata/whatsapp
npm ci --ignore-scripts
node --test
```

O pareamento é local e interativo. Nunca execute pareamento em CI ou cloud,
nunca salve a sessão no Git e nunca publique QR/código.

## A mensagem não foi enviada

Ausência de mensagem não significa ausência de atividade. Verifique primeiro:

1. a fonte oficial no Canvas;
2. se a coleta foi completa;
3. a janela BRT e o corte noturno;
4. estado, lease e outbox;
5. autorização explícita de entrega;
6. confirmação técnica do WhatsApp.

Um ACK confirma o contrato técnico de envio; não confirma leitura humana nem
substitui o Canvas.

## Problema em cloud

Não tente “consertar” produção por tentativa. Pare a entrega, registre somente
logs sanitizados e consulte [`cloud.md`](cloud.md) e
[`deploy-gcp.md`](deploy-gcp.md). Qualquer mudança de Job, Scheduler, IAM,
Secret Manager, GCS ou imagem exige autorização do titular e read-back.

## Como reportar

Abra uma issue com fixture sintética, versão/commit e saída sanitizada. Para
vulnerabilidades, siga [`../SECURITY.md`](../SECURITY.md). Não inclua dados de
estudantes, nomes de grupos, tokens, sessões ou URLs assinadas.
