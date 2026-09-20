# Suricata (pacote)

Bot público de avisos coletivos da turma no WhatsApp: consulta atividades
públicas do Canvas, decide o que é novidade e entrega no grupo autorizado —
nunca dados individuais, nunca comandos vindos do grupo, nunca segredo no Git.

## Os três modos

| Modo | O que faz | Envia? |
|---|---|---:|
| `shadow` | Probe local: emite um JSON de saúde e termina. Zero-config, usada pelo CI e pelo Docker. | Não |
| `demo` | Rodada offline com fixtures congeladas; planeja e imprime, sem Canvas/estado/entrega. | Não |
| `rodada` | Caminho canônico de produção: Canvas → planejamento → outbox → ponte WhatsApp. | Só com os 3 gates (entrega ligada + destino válido + janela BRT) |

O Dockerfile desta pasta fixa `ENTRYPOINT ["python3", "-m", "suricata"]` e
`CMD ["--mode", "shadow"]` — sem sobrescrever o comando, o container só
reporta saúde.

## Por onde andar

- Tutorial progressivo, sem efeitos: [`docs/guia.md`](../docs/guia.md)
- Operação, configuração e deploy: [`docs/operacao.md`](../docs/operacao.md)
- Como contribuir: [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- Índice geral: [`docs/README.md`](../docs/README.md)
- Ponte Node/WhatsApp: [`whatsapp/README.md`](whatsapp/README.md)
- Fronteira de infraestrutura: [`infra/README.md`](infra/README.md)

A configuração vem do ambiente do processo (variáveis `SURICATA_*`); não existe arquivo de configuração.
