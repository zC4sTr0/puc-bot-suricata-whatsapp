<div align="center">

<img src="docs/img/banner.svg" width="640" alt="PUC Bot da Suricata" />

# PUC Bot da Suricata

**Avisos acadêmicos coletivos no WhatsApp para estudantes da PUC Minas.**

[![CI](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml/badge.svg)](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)

[Começar](#começar) · [Como funciona](#como-funciona) · [Privacidade](docs/privacidade.md) · [Contribuir](#contribuir)

</div>

> Projeto independente e não oficial da PUC Minas. Confirme prazos e regras no Canvas e nos canais oficiais da disciplina.

## Para que serve

A Suricata lê atividades coletivas disponíveis no Canvas, organiza provas, quizzes e tarefas e pode avisar um grupo autorizado do WhatsApp. Não lê notas, faltas, submissões ou respostas.

O modelo atual é coletivo: uma instância atende um destino autorizado.

## Começar

O primeiro contato não precisa de token, Canvas ao vivo ou WhatsApp:

```bash
git clone https://github.com/zC4sTr0/suricata-whatsapp
cd suricata-whatsapp
python -m suricata --mode demo
```

A demo usa dados fictícios, não envia nada e não prova que uma conta real está funcionando.

Para validar o checkout:

```bash
python -m pytest -q
```

Veja o [guia rápido](docs/guia.md) para os outros modos.

## Como funciona

1. O Canvas fornece atividades coletivas.
2. Python classifica e planeja os avisos.
3. Estado, horário e autorização decidem se há envio.
4. Node conversa com o WhatsApp.
5. Um ACK válido confirma a entrega e evita duplicidade.

O processo pode ser acordado regularmente e ainda assim ficar em silêncio por falta de novidade, coleta incompleta, horário fechado ou autorização ausente.

## Segurança

- Demo offline com dados sintéticos.
- Entrega desligada por padrão.
- Tokens, sessões, QR, destinos e estado ficam fora do Git.
- Canvas continua sendo a fonte oficial.
- Uma suíte verde não prova acesso ao Canvas, Cloud Run, WhatsApp ou entrega real.

Leia [privacidade](docs/privacidade.md) e [configuração](docs/configuracao.md) antes de operar uma instância.

## Documentação

- [Guia](docs/guia.md)
- [Arquitetura](docs/arquitetura.md)
- [Configuração](docs/configuracao.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Deploy autorizado](docs/deploy-gcp.md)

## Contribuir

Abra uma issue sem tokens, QR, sessões, JIDs, dados de estudantes, capturas do Canvas ou logs de produção. Use fixtures fictícias e descreva o comportamento esperado. O código usa a [licença MIT](LICENSE).
