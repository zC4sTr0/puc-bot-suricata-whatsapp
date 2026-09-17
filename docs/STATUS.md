# Status Suricata

Código local: **não verificado no clone limpo** — a cópia foi materializada e aguarda execução dos gates no novo repositório.

Infraestrutura: **verificada por read-back em 2026-09-17** — projeto Suricata `ACTIVE`, Job principal `Ready=True`, Scheduler único `ENABLED`, Artifact Registry e service account no namespace Suricata. IAM least-privilege não verificado.

Produção e entrega: **não verificada para o novo repositório** — o Job atual está no digest conhecido do repositório acadêmico; a origem independente ainda precisa ser construída, publicada e ligada ao Job por procedimento de corte.

Última verificação: 2026-09-17; evidências: read-back Cloud Run/Scheduler/Artifact Registry/Secret Manager e testes locais no repositório de origem. Nenhum segredo foi lido.
