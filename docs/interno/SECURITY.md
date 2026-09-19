# Segurança

Ameaças principais: vazamento de token/sessão, mistura com o Bot Telegram, exposição de estado pessoal, envio para destino errado, duplicata após crash, ACK falso, corrida de estado e deploy de origem não rastreável.

Controles: allowlist pública do Canvas; validação de origem; subprocesso Node com ambiente mínimo; `.gitignore`, `.dockerignore` e `.gcloudignore`; lease/fencing; outbox idempotente; ACK vinculado ao `message_id`; corte BRT antes de claim/ponte; recursos GCP com prefixo Suricata; testes adversariais; imagem por digest; rollback por digest anterior.

Qualquer segredo encontrado deve ser removido do artefato sem ser impresso e o incidente deve ser registrado sanitizadamente.
