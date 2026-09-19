<div align="center">

<img src="docs/img/banner.svg" width="640" alt="PUC Bot da Suricata" />

# PUC Bot da Suricata

**Avisos acadêmicos coletivos no WhatsApp para estudantes da PUC Minas.**

[![CI](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml/badge.svg)](https://github.com/zC4sTr0/suricata-whatsapp/actions/workflows/suricata.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)

[Começar](#começar) · [Como funciona](#como-funciona) · [Privacidade](docs/privacidade.md) · [Glossário](docs/glossario.md) · [Contribuir](#contribuir)

</div>

> **Importante:** o PUC Bot da Suricata é um projeto independente e não oficial da PUC Minas. Não representa, fala em nome de ou possui autorização institucional da universidade. Confirme sempre prazos e regras no Canvas e nos canais oficiais da sua disciplina.

## Para que serve

O bot lê informações **públicas e coletivas** disponíveis no Canvas — por exemplo, uma prova, um quiz ou uma tarefa com prazo — e pode avisar um grupo autorizado do WhatsApp. A ideia é reduzir a chance de a turma perder uma mudança ou um prazo, sem publicar notas, faltas, respostas ou situações individuais.

O modelo atual é **coletivo**: uma instância atende um destino de turma/grupo autorizado. Ele não é um assistente particular de cada estudante e não acessa o seu perfil, suas entregas ou suas notas.

A direção do projeto é permitir que **cada estudante opere o seu próprio bot**: sua conta/projeto cloud, seu token do Canvas, seu número pessoal para a configuração e um número/chip separado para a conta do bot. Depois do pareamento e da confirmação, essa pessoa poderá escolher os cursos e colocar o bot nos grupos que administra ou para os quais tem autorização. Esse é o objetivo do produto, não uma capacidade já disponível neste commit.

## Começar

Você pode conhecer o fluxo sem token, conta, Canvas ao vivo ou WhatsApp:

```bash
git clone https://github.com/zC4sTr0/suricata-whatsapp
cd suricata-whatsapp
python -m suricata --mode demo
```

O modo `demo` usa dados fictícios congelados e mostra as mensagens que seriam planejadas. Ele não envia nada e não prova que uma conta real do Canvas ou uma sessão do WhatsApp esteja funcionando.

Para validar o checkout local:

```bash
python -m pytest -q
```

Os testes verificam contratos locais do projeto. Uma suíte verde não comprova acesso ao Canvas, funcionamento do Google Cloud, conexão do WhatsApp ou entrega para um grupo real.

O [guia passo a passo](docs/guia.md) explica os modos locais, a origem dos avisos e o que é necessário para uma operação autorizada.

## Como funciona

1. O Canvas fornece atividades e anúncios que podem ser vistos coletivamente.
2. O bot identifica novidades e organiza o aviso por disciplina, tipo e data.
3. Regras de horário e segurança decidem se o aviso pode sair.
4. O aviso é preparado para um grupo autorizado.
5. A ponte do WhatsApp só é chamada quando a entrega está explicitamente habilitada; a confirmação da entrega é vinculada ao mesmo aviso para evitar duplicidade.

Uma **rodada** é uma execução desse ciclo. Em uma operação configurada, o agendador pode iniciar rodadas regularmente, inclusive quando nenhuma mensagem será enviada. Acordar não significa enviar: o bot pode ficar em silêncio por horário, falta de novidade, coleta incompleta ou ausência de autorização.

### Exemplos de avisos

- **Prova:** há uma avaliação publicada ou com prazo próximo, com a data que o Canvas informa.
- **Quiz:** há um quiz disponível ou prestes a abrir, sem iniciar tentativa nem revelar resposta.
- **Tarefa/entrega:** existe uma atividade com prazo, com link público e data quando esses dados estão disponíveis.
- **Agenda manual:** um operador autorizado pode registrar uma informação coletiva que não está no Canvas, como uma prova anunciada em aula. Isso não transforma uma anotação em comunicado oficial.

A mensagem deve indicar a origem — Canvas ou agenda manual — para que a turma saiba de onde veio a informação. Se o Canvas estiver indisponível ou não trouxer dados suficientes, o bot não deve tratar isso como “não há atividade”. Confira a fonte oficial.

### Horários e limites

As regras atuais usam o horário de Brasília. O código possui janelas de entrega e corte noturno; uma rodada pode consultar e registrar um relatório sem enviar mensagem. Não interprete um aviso ausente como prova de que não existe tarefa: confira o Canvas.

O bot não decide se você deve estudar, não dá nota, não corrige atividade e não substitui professor, coordenação ou secretaria. Ele organiza avisos; a responsabilidade de confirmar o conteúdo continua sendo da pessoa estudante.

## O que fica protegido

- Não coletamos notas, frequência, submissões, tentativas, respostas ou senhas de quiz para montar avisos.
- Token do Canvas, sessão/QR do WhatsApp, destinos e estado operacional ficam fora do repositório e não devem ser publicados em issues, logs ou PRs.
- O modo de demonstração é offline e usa apenas dados sintéticos.
- Um link público ou uma atividade visível para a turma ainda pode conter dados pessoais publicados por terceiros. Por isso, não copie para o grupo nem para o Git informações que não sejam necessárias.

Leia os [limites de privacidade](docs/privacidade.md) antes de configurar qualquer instância.

## O que é preciso para uma operação real

Uma operação real não é ativada apenas clonando o projeto. Ela requer, no mínimo, autorização do responsável pelo destino, uma credencial adequada do Canvas, armazenamento protegido, uma sessão WhatsApp mantida fora do Git e confirmação do destinatário. Não peça nem publique credenciais neste repositório.

A documentação técnica está organizada em [`docs/`](docs/README.md). O deploy em nuvem é assunto de operador autorizado, não um passo necessário para testar o demo como estudante.

## Contribuir

Para sugerir melhoria, abra uma issue sem incluir token, QR, sessão, JID, conteúdo de turma identificável, captura do Canvas ou log de produção. Prefira exemplos fictícios e descreva o comportamento esperado. O código é distribuído sob a [licença MIT](LICENSE).

## Documentação

- [Guia](docs/guia.md): experimentar o projeto e entender os modos locais.
- [Arquitetura](docs/arquitetura.md): fronteiras técnicas e regras do runtime.
- [Privacidade](docs/privacidade.md): dados usados, não usados e limites da proteção.
- [Glossário](docs/glossario.md): termos do Canvas, dos avisos e do projeto.
- [Índice da documentação](docs/README.md): mapa das páginas públicas e internas.
