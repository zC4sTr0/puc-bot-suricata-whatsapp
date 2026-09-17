# syntax=docker/dockerfile:1
# Imagem construída com `gcloud builds submit suricata` (contexto = esta pasta).
# O runtime padrão é shadow: somente leitura, sem config, rede ou credencial.
# Risco residual: a tag da base não é digest-pinned; não há digest verificado disponível neste escopo.
FROM node:22-bookworm-slim

ENV NODE_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        python3 git openssh-client ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin suricata

WORKDIR /app

# O contexto já é suricata/: os caminhos COPY são relativos a ele.
COPY whatsapp/package.json whatsapp/package-lock.json ./suricata/whatsapp/
RUN npm ci --omit=dev --prefix ./suricata/whatsapp \
    && npm cache clean --force

COPY . ./suricata/

# A sessão Baileys nunca faz parte do contexto nem da imagem.
RUN chown -R suricata:suricata /app
USER suricata

LABEL org.opencontainers.image.title="Suricata College" \
      org.opencontainers.image.description="Runtime isolado do bot WhatsApp Suricata" \
      org.opencontainers.image.source="suricata/"

# Produção: `--mode rodada` (configurado só por ambiente; SURICATA_ENTREGA=desligada é sombra).
ENTRYPOINT ["python3", "-m", "suricata"]
CMD ["--mode", "shadow"]
