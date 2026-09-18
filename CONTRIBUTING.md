# Contribuindo com a Suricata

Este guia é a versão humana do `AGENTS.md`: as mesmas regras, escritas para
pessoas. Se algo aqui conflitar com o `AGENTS.md`, o `AGENTS.md` vence.

O repositório contém somente a Suricata — o bot público de avisos acadêmicos
no WhatsApp. O repositório acadêmico, o Bot Telegram, sessões WhatsApp e
dados pessoais ficam fora daqui.

## Pré-requisitos

- Python 3.11+ (o projeto é stdlib puro, sem dependências).
- Node.js para a ponte WhatsApp e os testes `.mjs`.

A ponte Node é testada por `node --test`; instale as dependências dela antes,
sem executar scripts de instalação:

```bash
npm ci --prefix suricata/whatsapp --ignore-scripts
```

## Matriz de validação local

Rode tudo antes de considerar uma mudança pronta, a partir da raiz do repo:

```bash
python -m compileall -q suricata
python -m pytest -q
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
python -m suricata --mode shadow
```

Cada comando cobre um ângulo: `compileall` pega erro de sintaxe; `pytest` e
`unittest` rodam a suíte de contratos (com sobreposição incluída); `node --test`
cobre a ponte WhatsApp; `shadow` prova que o pacote importa e o entrypoint
emite o JSON de saúde, sem tocar Canvas, estado ou entrega. Se algum falhar,
corrija antes de seguir; não entregue com a matriz vermelha.

Em mudanças de infraestrutura, faça também `git diff --check`, uma varredura de
segredos e um canário sem entrega.

## Padrão de contribuição

O projeto avança por fatias pequenas e verificáveis. O fluxo que funciona:

1. **Teste primeiro.** Antes de mexer em produção, escreva o teste de
   compatibilidade: caracterize o comportamento atual da seam que você vai
   tocar (use o padrão `assertIs` e testes de caracterização das seams, como
   nos `*_compatibility.py`) e deixe-o verde contra o código atual.
2. **Refatore em fatia pequena.** Uma mudança por commit, mínima, que mantém
   os contratos. Se o diff cresceu além do revisável, divida.
3. **Commits descritivos no estilo convencional**: `refactor: isolate ...`,
   `test: ...`, `fix: ...`. Pequenos, sem arquivos ignorados.

Trabalhe em branch e não reescreva histórico compartilhado.

## O que NUNCA fazer

- **Nunca comite segredo**: token, QR, `auth.json`, cookies, `.wa-auth/`,
  logs, capturas, bases. Credenciais vivem em Secret Manager ou variáveis
  `SURICATA_*` fora do repo.
- **Nunca pareie, envie ou toque Cloud na validação local.** Pareamento de
  sessão WhatsApp, envio real, alteração de IAM, Scheduler, Job ou produção
  exigem autorização explícita do titular e plano de rollback.
- **Nunca traga dados acadêmicos** nem código/paths/buckets/destinos do
  repositório acadêmico ou do Bot Telegram.
- **`SURICATA_ENTREGA` fica desligada por padrão.** O valor exato `ligada`
  só entra em produção com autorização. Qualquer outro valor entrega
  desligada.
- **Nunca envie mensagem real na validação local.** Não existe "só um teste de
  envio real"; a validação offline é `shadow`, `demo` e a suíte de testes.

O runtime deve falhar fechado quando faltarem configuração, estado, lease, ACK
ou autorização explícita de entrega. Não "conserte" esse comportamento.

## Propor uma mudança

Abra um PR com:

1. **Escopo**: o que muda e por quê, em uma frase por fatia.
2. **Provas**: a saída dos cinco comandos da matriz, rodada após a mudança.
3. **Limitações**: o que o PR não cobre, riscos conhecidos e o que ficou para
   depois.

PRs passam por revisão independente antes do merge squash. Se a mudança afeta
a entrega em produção, diga isso explicitamente no PR — sem autorização, o
merge espera.
