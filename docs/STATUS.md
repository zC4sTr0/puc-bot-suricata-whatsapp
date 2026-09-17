# Status Suricata

Código local: **verificado no clone independente** — `compileall`, `pytest`, `unittest`, Node e shadow passaram no commit `203f0a3`.

Infraestrutura: **verificada por read-back em 2026-09-17** — projeto Suricata `ACTIVE`, Job principal `Ready=True`, Scheduler único `ENABLED`, Artifact Registry e service account no namespace Suricata. IAM least-privilege não verificado.

Build independente: **concluído** — Cloud Build `1e200017-3da4-4c6e-8302-12f478b2e636`, commit `203f0a3`, imagem `southamerica-east1-docker.pkg.dev/suricata-college-20260913/suricata/suricata`, digest `sha256:6071de09eb357e35f091173407760aabda091b5eb8f0f3e2c533dae9caa32f98`. O primeiro destino tentado estava incorreto e falhou sem alterar produção; o segundo usou o repositório Artifact Registry confirmado e passou.

Canário: **concluído sem entrega** — Job existente `suricata-canario-prod`, geração `2`, digest novo, args `--mode rodada`, `SURICATA_ENTREGA=desligada`, `maxRetries=0`, timeout `300s`; execução `suricata-canario-prod-8mx8z` terminou `succeededCount=1` em aproximadamente 17s. Nenhum Scheduler aponta para o canário.

Produção e entrega: **não cortadas** — o Job `suricata-rodada` continua no digest anterior `sha256:9622db22436d366a2b1b6224479eb5b3b6c5a66da4f5a8fe5da468216de763c3`, com args `--mode rodada`; o único Scheduler continua `suricata-rodada-10min`. Nenhuma entrega real foi ativada a partir do novo repo.

GitHub: **privado e publicado** em `https://github.com/zC4sTr0/suricata-whatsapp`; PR `#1` aberto, CI verde, aguardando review independente antes do merge. Nenhum segredo foi lido.
