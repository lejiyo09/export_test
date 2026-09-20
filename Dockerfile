FROM node:24-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Cobalt's current monorepo declares pnpm 9.6.0. Install it directly instead
# of relying on Corepack, which is absent in this Render base image.
RUN npm install -g pnpm@9.6.0

RUN git clone --depth 1 --branch main https://github.com/imputnet/cobalt.git /build/cobalt \
 && cd /build/cobalt \
 && pnpm install --frozen-lockfile \
 && mkdir -p /opt/cobalt-api \
 && cp -a api/. /opt/cobalt-api/ \
 && cp package.json pnpm-lock.yaml pnpm-workspace.yaml /opt/cobalt-api/ 2>/dev/null || true \
 && cd /opt/cobalt-api \
 && pnpm install --prod --frozen-lockfile

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates
COPY start.sh .
RUN chmod +x start.sh

ENV PORT=8080
ENV YTDLP_JS_RUNTIME=node
ENV COBALT_URL=http://127.0.0.1:9000
ENV API_URL=http://127.0.0.1:9000/
ENV API_PORT=9000
ENV API_LISTEN_ADDRESS=127.0.0.1

EXPOSE 8080

CMD ["/app/start.sh"]
