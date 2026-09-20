# Guia rápido

A Suricata transforma atividades coletivas do Canvas em avisos para um grupo autorizado. Ela não lê notas, submissões ou respostas e não substitui o Canvas.

## 1. Rodar sem efeitos externos

Requisitos: Python 3.11+. Node só é necessário para os testes da ponte WhatsApp.

```bash
git clone https://github.com/zC4sTr0/suricata-whatsapp
cd suricata-whatsapp
python -m suricata --mode demo
```

A demo usa dados fictícios, relógio fixo e entrega desligada.

## 2. Validar o checkout

```bash
python -m suricata --mode shadow
python -m compileall -q suricata
python -m pytest -q

cd suricata/whatsapp
npm ci --ignore-scripts
node --test
```

Esses comandos validam contratos locais. Não comprovam Canvas, Cloud Run, sessão WhatsApp ou entrega real.

## 3. Entender os modos

| Modo | Uso | Envia mensagem? |
|---|---|---:|
| `shadow` | verificar o entrypoint | não |
| `demo` | mostrar uma rodada fictícia | não |
| `rodada` | caminho de operação | somente com todos os gates |

## 4. Horários

O relógio é `America/Sao_Paulo`.

- **07:00:** reabre a manhã.
- **12:00:** pode avisar prova ou quiz do dia seguinte.
- **18:00:** lembrete principal da véspera.
- **21:00:** encerra a janela de envio.

O agendador pode acordar o processo a cada 10 minutos; isso não significa que uma mensagem será enviada.

## 5. Rodada local sem entrega

```bash
SURICATA_ESTADO_URI=./tmp-estado \
SURICATA_CANVAS_TOKEN=falso \
SURICATA_ENTREGA=desligada \
python -m suricata --mode rodada
```

Use somente estado descartável. Sessão WhatsApp, tokens e destinos ficam fora do repositório.

## 6. Operação real

Uma operação real exige token do Canvas, estado protegido, destino confirmado, sessão WhatsApp externa, janela aberta e ACK válido. A entrega só é habilitada com `SURICATA_ENTREGA=ligada` e autorização do responsável pelo destino.

Nunca faça pareamento em CI ou Cloud Run e nunca publique QR, sessão, token ou JID.

Para configuração detalhada, leia [`configuracao.md`](configuracao.md). Para operação em nuvem, leia [`deploy-gcp.md`](deploy-gcp.md).
