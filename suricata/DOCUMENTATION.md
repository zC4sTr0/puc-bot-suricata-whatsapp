# Documentação do Suricata

Índice humano para manutenção segura. A documentação não autoriza deploy, envio, pareamento ou alteração de infraestrutura.

## Roteamento

1. Produto, fronteiras e comandos offline: [`README.md`](README.md).
2. Entrada, modos e configuração: [`ARCHITECTURE.md`](ARCHITECTURE.md).
3. Contratos que uma refatoração deve preservar: [`../docs/CONTRACTS.md`](../docs/CONTRACTS.md).
4. Pré-voo, parada e gates humanos: [`RUNBOOK.md`](RUNBOOK.md).
5. Testes e limites da evidência: [`tests/README.md`](tests/README.md).
6. WhatsApp/Node: [`whatsapp/README.md`](whatsapp/README.md).
7. Índice geral, estado e deploy: [`../docs/README.md`](../docs/README.md), [`../docs/STATUS.md`](../docs/STATUS.md) e [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).
8. Plano histórico e decisões datadas: [`../docs/PLANO-SURICATA-WHATSAPP.md`](../docs/PLANO-SURICATA-WHATSAPP.md).
9. Isolamento declarativo: [`infra/README.md`](infra/README.md) e [`infra/isolamento.json`](infra/isolamento.json).

## Distinções obrigatórias

- **Probe `shadow`:** default do Docker; emite saúde local e termina sem Canvas, estado ou entrega.
- **`demo`:** rodada offline com fixtures congeladas e entrega desligada; para estudo, sem variáveis.
- **`rodada`:** caminho funcional canônico; configuração por ambiente e efeitos condicionados por entrega, estado, sessão, ACK e janela BRT.

Os modos `sentinela`, `grupos` e `teste-envio` foram removidos na simplificação de modos de 2026-09-18; o histórico vive no git.

Nomes de Job e Scheduler são evidência operacional somente quando acompanhados de data e read-back. O plano e o inventário local divergem; consulte [`RUNBOOK.md`](RUNBOOK.md) antes de usar qualquer nome.

## Fonte de verdade por assunto

| Assunto | Fonte primária | Limite |
|---|---|---|
| argumentos e modos | `suricata/entrypoint.py` | implementação local, não nuvem |
| empacotamento | `suricata/Dockerfile` | não prova build/deploy |
| configuração funcional | `suricata/rodada/config.py`, `suricata/rodada/__init__.py` | ambiente efetivo precisa de read-back |
| isolamento | `suricata/infra/isolamento.json` | fotografia datada, não estado atual |
| decisão e sequência do produto | `docs/PLANO-SURICATA-WHATSAPP.md` | contém histórico; fatos antigos devem ser datados |
| prova local | `suricata/tests/README.md` e testes | não prova serviços externos |

Quando houver conflito, preserve as versões com a data e marque o ponto como `não verificado`; não escolha o nome mais plausível nem transforme intenção do plano em estado atual.
