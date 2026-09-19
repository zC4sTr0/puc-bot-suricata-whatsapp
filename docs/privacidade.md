# Privacidade e limites

O **PUC Bot da Suricata** é um projeto independente e não oficial da PUC Minas. Esta página explica o comportamento pretendido do repositório; não é uma política institucional da universidade nem substitui uma avaliação jurídica ou um aviso de privacidade do operador de uma instância.

## O que o modelo atual faz

O modelo atual é **coletivo**. Uma instância autorizada consulta informações que podem ser vistas pela turma no Canvas e prepara avisos para um grupo de WhatsApp definido pelo operador. O objetivo é comunicar fatos acadêmicos coletivos, como a publicação de uma prova, quiz ou tarefa.

A origem deve aparecer no fluxo: o dado pode vir do Canvas ou de uma agenda manual preenchida por um operador autorizado. Uma anotação manual é uma fonte informada pelo operador, não uma confirmação institucional.

## O que não deve ser coletado para avisos

O bot não precisa de informações individuais para cumprir esse objetivo. Não use o projeto para coletar ou publicar:

- notas, frequência, presença ou desempenho;
- submissões, tentativas, respostas ou senha de quiz;
- mensagens privadas, contatos pessoais ou perfil de estudante;
- QR code, sessão, token ou senha de qualquer serviço;
- dados pessoais copiados de uma página apenas porque estavam visíveis.

Uma atividade pode ter um link público e ainda assim conter informação pessoal. “Público no Canvas” significa acessível naquele contexto; não significa que deve ser republicado em qualquer lugar.

## O que fica sob responsabilidade do operador

Para uma instância real, o operador deve definir finalidade e acesso, obter autorização para o destino, guardar credenciais fora do Git, limitar registros, controlar quem pode alterar a agenda e remover acessos quando eles não forem mais necessários. O repositório não concede autorização para acessar cursos, grupos ou contas.

A sessão do WhatsApp, o QR code, o token do Canvas, os destinos e o estado da operação são materiais sensíveis. Nunca os coloque em issues, PRs, fixtures, capturas de tela, logs públicos ou exemplos copiados do ambiente real. Use valores sintéticos nos testes.

O PUC Bot da Suricata não garante, sozinho, anonimização, segurança de uma conta do WhatsApp, conformidade institucional ou cumprimento da legislação. A infraestrutura, o provedor, o operador e os serviços externos podem manter registros próprios. Consulte os termos e políticas desses serviços.

## Coletivo hoje, individual no futuro

O bot atual não é um bot particular por estudante. Ele não seleciona cursos pessoais, não entrega avisos em um destino privado individual e não oferece um painel de consentimento ou revogação por pessoa.

Para existir um modelo individual responsável, seria necessário implementar e validar, entre outros pontos:

- consentimento explícito e informado;
- escopo de cursos e fontes por pessoa;
- destino privado confirmado;
- revogação e exclusão de dados;
- controle de acesso, retenção e auditoria;
- comunicação clara de erros, origem e atualização dos dados.

Esses requisitos são uma evolução do produto, não uma capacidade já oferecida por este repositório.

## Como testar sem dados pessoais

Use o modo demo:

```bash
python -m suricata --mode demo
```

Ele usa uma fonte Canvas congelada e fictícia, não acessa a rede e não envia WhatsApp. O resultado prova apenas o planejamento local do exemplo. Para prazos e situação real da sua turma, confira o Canvas e os canais oficiais.

Se encontrar um problema, reporte somente exemplos inventados e descreva o comportamento observado. Não envie dados de estudantes para os mantenedores.
