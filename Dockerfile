# syntax=docker/dockerfile:1
# Base digest-pinned (sha256:83f487e...) para builds reproduzíveis.
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5
ENV NODE_ENV=production PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install --no-install-recommends -y python3 git ca-certificates tzdata && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 --shell /usr/sbin/nologin suricata
WORKDIR /app
COPY suricata/whatsapp/package.json suricata/whatsapp/package-lock.json /app/suricata/whatsapp/
RUN npm ci --omit=dev --ignore-scripts --prefix /app/suricata/whatsapp && npm cache clean --force
COPY suricata /app/suricata
RUN chown -R suricata:suricata /app
USER suricata
LABEL org.opencontainers.image.title="Suricata College" org.opencontainers.image.description="Runtime isolado do bot WhatsApp Suricata"
ENTRYPOINT ["python3", "-m", "suricata"]
CMD ["--mode", "shadow"]
