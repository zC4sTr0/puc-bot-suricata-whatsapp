# Privacidade e limites

A Suricata é um projeto independente e não oficial da PUC Minas. Esta página descreve o comportamento do software; não é política institucional nem avaliação jurídica.

## O que o bot usa

O modelo atual consulta informações coletivas visíveis no Canvas e prepara avisos para um grupo autorizado. A origem pode ser o Canvas ou uma agenda manual preenchida pelo operador.

## O que não deve ser coletado

Não use o projeto para coletar ou publicar:

- notas, frequência, desempenho ou perfil individual;
- submissões, tentativas, respostas ou senhas de quiz;
- mensagens privadas ou contatos pessoais;
- token, QR code ou sessão de qualquer serviço;
- dados pessoais copiados de uma página apenas porque estavam visíveis.

Uma atividade visível para a turma ainda pode conter informação pessoal. Público no Canvas não significa livre para republicação.

## Responsabilidade do operador

O operador deve ter autorização para a fonte e o destino, guardar credenciais fora do Git, limitar registros, controlar alterações e remover acessos quando necessário. O repositório não concede autorização para cursos, grupos ou contas.

Sessão WhatsApp, QR code, token do Canvas, destinos e estado operacional são materiais sensíveis. Não os coloque em issues, PRs, fixtures, capturas, logs públicos ou exemplos reais.

## Testar com segurança

```bash
python -m suricata --mode demo
```

A demo usa dados fictícios, não acessa a rede e não envia WhatsApp. Para dados reais, confira sempre o Canvas e os canais oficiais.
