# Suricata College — WhatsApp

[![CI](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml/badge.svg)](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

## 1. O que faz

A Suricata consulta atividades públicas do Canvas, identifica novidades coletivas e prepara avisos simples para o grupo autorizado da turma. O fluxo é Python → outbox/estado → ponte Node/Baileys → WhatsApp, com ACK antes de marcar uma mensagem como enviada.

## Quickstart

Std lib pura: zero `pip install`. Do clone ao primeiro aviso:

```bash
python -m suricata --mode shadow   # probe zero-config
python -m suricata --mode demo     # avisos planejados offline com fixtures, entrega desligada
python -m pytest -q                # suíte completa
```

Os testes `.mjs` (ponte Node/Baileys) exigem Node 20+ e a dependência instalada
uma vez por clone:

```bash
npm ci --prefix suricata/whatsapp --ignore-scripts
```

Ou deixe um comando fazer tudo: `python scripts/bootstrap.py` verifica Python/Node,
instala a dependência Node e roda compileall, pytest e shadow.

Para evoluir daqui, siga a [trilha do estudante](docs/TRILHA-ESTUDANTE.md) —
quatro níveis, de testes verdes até uma rodada local com estado em diretório.
Regras de contribuição em [CONTRIBUTING.md](CONTRIBUTING.md); as variáveis
`SURICATA_*` estão documentadas com comentários em [.env.example](.env.example).

## 2. O que nunca faz

Nunca publica notas, frequência, atrasos, entregas individuais ou qualquer situação pessoal. Não recebe comandos acadêmicos, não envia atividades ao Canvas e não grava sessão, QR ou segredo no Git/imagem/log.

## 3. Teste local sem efeitos

```bash
python -m suricata --mode shadow
python -m compileall -q suricata
python -m pytest -q suricata/tests
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
```

`shadow` é uma probe local. Para o caminho funcional sem entrega, use fixtures e `SURICATA_ENTREGA=desligada`; nunca use JID ou sessão real.

## 4. Modos

- `shadow`: probe sem Canvas, estado ou entrega.
- `sentinela`: compatibilidade funcional com `--config` explícito.
- `rodada`: caminho canônico Canvas → planejamento → outbox → ponte.
- `grupos`: inventário read-only da sessão.
- `teste-envio`: efeito externo; proibido em validação.

## 5. Produção

O alvo documentado é o projeto GCP Suricata, região `southamerica-east1`, Cloud Run Job `suricata-rodada` e Scheduler `suricata-rodada-10min`. O estado operacional e os valores atuais devem ser conferidos em `docs/STATUS.md` e por read-back, nunca inferidos deste texto.

O índice de documentação está em [`docs/README.md`](docs/README.md); ele separa produto, operação, segurança, deploy, continuidade e histórico.

Para onboarding humano, leia nesta ordem: `AGENTS.md` → [`docs/STATUS.md`](docs/STATUS.md) → [`docs/CONTRACTS.md`](docs/CONTRACTS.md) → [`suricata/README.md`](suricata/README.md) → [`suricata/ARCHITECTURE.md`](suricata/ARCHITECTURE.md) → [`suricata/RUNBOOK.md`](suricata/RUNBOOK.md) → [`suricata/tests/README.md`](suricata/tests/README.md). Planos históricos não substituem read-back.

## 6. Mensagens, Canvas, estado e Node

Mensagens são planejadas em `suricata/publico.py`/`planejamento.py` e orquestradas em `suricata/rodada.py`. Canvas é consultado por `suricata/canvas.py` e `coleta.py`, sempre com dados públicos. Estado, lease e outbox ficam em `suricata/storage/`, `estado.py`, `outbox.py` e `persistencia_rodada.py`. A ponte está em `suricata/bridge.py`; o Node está em `suricata/whatsapp/`.

## 7. Configuração sem segredo

Use variáveis de ambiente ou Secret Manager: `SURICATA_CANVAS_TOKEN`, `SURICATA_ESTADO_URI`, `SURICATA_ENTREGA`, `SURICATA_GRUPO_JID`, `SURICATA_DESTINOS_JSON`, `SURICATA_LEASE_MINUTOS` e `SURICATA_WA_AUTH_DIR`. Nunca coloque valores reais em JSON, YAML, logs ou argumentos.

## 8. Testar, implantar e verificar

O CI está em `.github/workflows/suricata.yml`. O build usa o `Dockerfile` da raiz e o lockfile Node. Para deploy, siga `docs/DEPLOYMENT.md`: build por digest, read-back do Job/Scheduler, canário desligado, rollback pela imagem anterior e nenhum scheduler duplicado.

## 9. Retomada e continuidade

O roteiro executável para um agente sem o histórico desta conversa está em
`docs/PLANO-CONTINUIDADE-INDEPENDENTE.md`. Ele deve ser lido junto com
`docs/PLANO-EXTRACAO-SURICATA.md` e `docs/STATUS.md`. O plano histórico
`docs/PLANO-SURICATA-WHATSAPP.md` é referência de contratos e não autoriza
comandos do Bot pessoal ou ações externas por cópia.

## 10. Parar e reverter

Não desligue recursos por suposição. Em incidente, desligue entrega no caminho autorizado, preserve estado/outbox e faça read-back. Rollback significa apontar o Job para o digest anterior conhecido, verificar a configuração e observar a próxima execução; nunca reescreva histórico nem apague estado.

## 11. Retomada rápida

Um agente novo deve começar por `AGENTS.md`, `docs/PLANO-CONTINUIDADE-INDEPENDENTE.md`, `docs/PLANO-EXTRACAO-SURICATA.md` e `docs/STATUS.md`, executar a matriz de verificação e continuar a primeira etapa pendente.
