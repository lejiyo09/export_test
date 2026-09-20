FROM node:26-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ffmpeg git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN corepack enable \
 && corepack prepare pnpm@9.6.0 --activate

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Cobalt API is used as the primary YouTube media extractor.
RUN git clone --depth 1 https://github.com/imputnet/cobalt.git /opt/cobalt \
 && cd /opt/cobalt \
 && pnpm install --frozen-lockfile

COPY app.py .
COPY templates ./templates
COPY start.sh .
RUN chmod +x start.sh

ENV PORT=8080
ENV YTDLP_JS_RUNTIME=node
ENV COBALT_URL=http://127.0.0.1:9001
ENV API_URL=http://127.0.0.1:9001/
ENV API_PORT=9001
ENV API_LISTEN_ADDRESS=127.0.0.1
ENV FORCE_LOCAL_PROCESSING=always
ENV DISABLED_SERVICES=

EXPOSE 8080

CMD ["/app/start.sh"]
