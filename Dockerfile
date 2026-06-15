FROM node:20-slim

# Instalar Python y dependencias de sistema
RUN apt-get update && apt-get install -y \
  python3 \
  python3-pip \
  chromium \
  git \
  && rm -rf /var/lib/apt/lists/*

# Establecer directorio de trabajo
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.23.0 --activate

# Copiar archivos de configuración de Node.js
COPY package*.json ./
RUN npm install
RUN npm install ts-node typescript @types/node nodemailer

# Copiar requirements de Python e instalar
COPY requirements.txt ./
RUN pip3 install -r requirements.txt --break-system-packages

# Optionally install Chromium and Xvfb for browser automation.
# Build with: docker build --build-arg OPENCLAW_INSTALL_BROWSER=1 ...
# Adds ~300MB but eliminates the 60-90s Playwright install on every container start.
# Must run after pnpm install so playwright-core is available in node_modules.
ARG OPENCLAW_INSTALL_BROWSER=""
RUN if [ -n "$OPENCLAW_INSTALL_BROWSER" ]; then \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends xvfb && \
      node /app/node_modules/playwright-core/cli.js install --with-deps chromium && \
      apt-get clean && \
      rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*; \
    fi

COPY . .
RUN pnpm build
# Force pnpm for UI build (Bun may fail on ARM/Synology architectures)
ENV OPENCLAW_PREFER_PNPM=1
RUN pnpm ui:build

# Variables de entorno por defecto
ENV STATE_DIR=/app/state
ENV CONFIG_DIR=/app/config

# Crear directorios necesarios
RUN mkdir -p /app/state /app/config

# Security hardening: Run as non-root user
# The node:22-bookworm image includes a 'node' user (uid 1000)
# This reduces the attack surface by preventing container escape via root privileges
USER node

# Start gateway server with default config.
# Binds to loopback (127.0.0.1) by default for security.
#
# For container platforms requiring external health checks:
#   1. Set OPENCLAW_GATEWAY_TOKEN or OPENCLAW_GATEWAY_PASSWORD env var
#   2. Override CMD: ["node","openclaw.mjs","gateway","--allow-unconfigured","--bind","lan"]
CMD ["node", "openclaw.mjs", "gateway", "--allow-unconfigured"]
