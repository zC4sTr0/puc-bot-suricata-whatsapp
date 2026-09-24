# Troubleshooting

- **Testes Python falham:** distinguir falha preexistente de regressão; não mascarar com skip.
- **npm ci falha:** a dependência Git `libsignal` exige rede; não inventar pacote/hash.
- **Docker não inicia:** conferir contexto na raiz e `CMD --mode shadow`.
- **Canvas falha:** não converter erro parcial em ausência.
- **Outbox pendente:** manter `pending` até ACK ou expiração; não forçar `sent`.
- **Scheduler executa sem mensagem:** normal quando não há evento elegível ou após o corte 21h.
- **Sessão logged_out:** parar entrega e seguir o gate humano de pareamento.
- **Job divergente:** listar e descrever recursos antes de atualizar; nunca criar segundo Scheduler por suposição.
- **Rodada com `sem_ack > 0`:** `eventos=[]` significa que não houve tentativa. Numa tentativa, leia no relatório e na dead-letter os campos sanitizados `failure_code` (`EMPTY_STDOUT`, `INVALID_JSON`, `TIMEOUT`, `SIGNAL_EXIT`, `NODE_TRANSPORT_ERROR`, `ACK_INCONSISTENT`), `phase`, `returncode`/`signal`, `duration_ms`, `stdout_bytes`, `stdout_linhas` e `stderr_bytes`. `Job Succeeded` só prova que o processo terminou; `OK_ACK` é a única evidência de entrega. Nunca registre stdout/stderr bruto, sessão, JID, texto, token ou payload.
