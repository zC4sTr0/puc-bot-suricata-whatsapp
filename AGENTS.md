# AGENTS.md — Suricata WhatsApp

## Escopo

Este repositório contém somente a Suricata: o bot público de avisos acadêmicos no WhatsApp. O repositório acadêmico, o Bot Telegram, sessões WhatsApp e dados pessoais ficam fora daqui.

## Antes de alterar

1. Leia `README.md`, `docs/PLANO-CONTINUIDADE-INDEPENDENTE.md`, `docs/PLANO-EXTRACAO-SURICATA.md` e `docs/STATUS.md`.
2. Preserve os contratos em `suricata/tests/` e `suricata/whatsapp/tests/`.
3. Nunca copie `academico/`, `periodos/`, `.canvas/`, `scripts/academico/`, capturas, materiais, logs, bases, QR, cookies, tokens, `auth.json` ou `.wa-auth/`.
4. Nunca introduza imports, caminhos, buckets, jobs, secrets ou destinos do Bot Telegram ou do repositório acadêmico.

## Validação obrigatória

```bash
python -m compileall -q suricata
python -m pytest -q
python -m unittest discover -s suricata/tests
node --test suricata/tests/*.mjs suricata/whatsapp/tests/*.mjs
python -m suricata --mode shadow
```

Antes de uma mudança de infraestrutura, faça `git diff --check`, a varredura de segredos e um canário sem entrega. O runtime deve falhar fechado quando faltarem configuração, estado, lease, ACK ou autorização explícita de entrega.

## Configuração e segredos

- Use variáveis `SURICATA_*` e Secret Manager; não grave valores em arquivos versionados.
- A autenticação WhatsApp deve ficar fora do repositório e ser fornecida por `SURICATA_WA_AUTH_DIR`.
- O publicador de agenda usa somente `SURICATA_ESTADO_URI`; não adicione destinos secundários por padrão.
- Não execute pareamento, envio real, alteração de IAM, Scheduler, Job ou produção sem autorização explícita do titular e plano de rollback.

## Git e deploy

- Trabalhe em branch; não reescreva histórico compartilhado.
- Commits devem ser pequenos, verificáveis e sem arquivos ignorados.
- Para GitHub, use repositório privado, PR e revisão independente antes do merge squash.
- Produção é o Job `suricata-rodada` e o Scheduler `suricata-rodada-10min` no namespace Suricata. Nunca crie um segundo Scheduler nem substitua o digest sem read-back.

## Plano de continuidade

O estado executável vive em `docs/PLANO-CONTINUIDADE-INDEPENDENTE.md`. Ao retomar, leia o registro de progresso e continue da primeira etapa não concluída; atualize evidência e bloqueios reais, sem declarar sucesso baseado apenas em intenção ou auto-relato.
