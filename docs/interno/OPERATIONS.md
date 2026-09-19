# Operações
> **Interno — não normativo para lançamento público.** Contém contratos e orientação operacional genérica; valores reais exigem read-back autorizado.


1. Ler `AGENTS.md`, `docs/historico/PLANO-EXTRACAO-SURICATA.md` e `docs/interno/STATUS.md`.
2. Conferir branch, status, diff e testes.
3. Para nuvem, confirmar projeto/região/Job/Scheduler e digest por read-back.
4. Em incidente, não reenviar nem forçar `sent`: preserve `pending`, ACK e geração.
5. Sessão caída exige o gate de pareamento humano; não copiar QR/auth para o Git.
6. Job parado exige verificar Scheduler, execução e relatório sanitizado.

Não use efeito externo como diagnóstico: a validação local é `shadow`/`demo`/testes; nunca ligue entrega nem crie recursos duplicados.
