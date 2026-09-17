# Troubleshooting

- **Testes Python falham:** distinguir falha preexistente de regressão; não mascarar com skip.
- **npm ci falha:** a dependência Git `libsignal` exige rede; não inventar pacote/hash.
- **Docker não inicia:** conferir contexto na raiz e `CMD --mode shadow`.
- **Canvas falha:** não converter erro parcial em ausência.
- **Outbox pendente:** manter `pending` até ACK ou expiração; não forçar `sent`.
- **Scheduler executa sem mensagem:** normal quando não há evento elegível ou após o corte 21h.
- **Sessão logged_out:** parar entrega e seguir o gate humano de pareamento.
- **Job divergente:** listar e descrever recursos antes de atualizar; nunca criar segundo Scheduler por suposição.
