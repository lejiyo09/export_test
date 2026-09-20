FROM node:24-bookworm-slim AS cobalt-build

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 make g++ git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g pnpm@9.6.0

WORKDIR /build/cobalt
RUN git clone --depth 1 --branch main https://github.com/imputnet/cobalt.git .

RUN pnpm install --prod --frozen-lockfile \
 && pnpm deploy --filter=@imput/cobalt-api --prod /prod/api \
 && cp -a .git /prod/api/.git

FROM node:24-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ffmpeg ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN npm install -g pnpm@9.6.0

WORKDIR /opt/cobalt-api
COPY --from=cobalt-build /prod/api/ ./
COPY --from=cobalt-build /prod/api/.git ./.git

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
