# Infraestrutura isolada do Suricata

Os manifestos e runbooks específicos do Suricata ficam aqui. Não copiar
configurações do Bot Telegram para este diretório.

Recursos planejados, todos independentes:

- projeto GCP próprio do Suricata;
- bucket de estado próprio;
- Artifact Registry próprio;
- service account runtime própria;
- secrets próprios (`suricata-canvas-token`, `suricata-whatsapp-auth` e demais
  necessários), sem reutilizar nomes do Bot Telegram;
- Jobs e schedulers com prefixo `suricata-`;
- IAM sem acesso de escrita aos recursos `academico-*`.

Nenhum recurso é criado por este arquivo. O provisionamento segue S0.0 do plano.