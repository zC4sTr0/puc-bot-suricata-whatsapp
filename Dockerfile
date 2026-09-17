# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim
ENV NODE_ENV=production PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install --no-install-recommends -y python3 git openssh-client ca-certificates tzdata && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 --shell /usr/sbin/nologin suricata
WORKDIR /app
COPY suricata/whatsapp/package.json suricata/whatsapp/package-lock.json /app/suricata/whatsapp/
RUN npm ci --omit=dev --ignore-scripts --prefix /app/suricata/whatsapp && npm cache clean --force
COPY suricata /app/suricata
RUN chown -R suricata:suricata /app
USER suricata
LABEL org.opencontainers.image.title="Suricata College" org.opencontainers.image.description="Runtime isolado do bot WhatsApp Suricata"
ENTRYPOINT ["python3", "-m", "suricata"]
CMD ["--mode", "shadow"]
