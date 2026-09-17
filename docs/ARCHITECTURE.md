# Arquitetura

```text
Cloud Scheduler → Cloud Run Job
  → Canvas (GET público)
  → coleta/normalização
  → planejamento público por destino
  → lease + memória + outbox
  → ponte Python → Node/Baileys
  → ACK confirmado → sent
```

Python é dono do estado e do contrato; Node executa somente a ponte WhatsApp. O corte em `America/Sao_Paulo` bloqueia mensagens a partir de 21:00. `shadow` não consulta serviços externos. `rodada` é o caminho funcional e só entrega quando a configuração, a janela, o estado e o ACK permitem.

A configuração real pertence ao ambiente do processo ou ao Secret Manager. O repositório contém apenas placeholders e manifestos sanitizados.
