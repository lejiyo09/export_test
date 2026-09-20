FROM node:26-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv ffmpeg git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Build the bgutil provider's token-generation script.
RUN git clone --depth 1 --branch 2.0.0 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-ytdlp-pot-provider \
 && cd /opt/bgutil-ytdlp-pot-provider/server \
 && npm ci --no-audit --no-fund \
 && npx tsc

COPY app.py .
COPY templates ./templates

ENV PORT=8080
ENV YTDLP_JS_RUNTIME=node
ENV BGUTIL_SERVER_HOME=/opt/bgutil-ytdlp-pot-provider/server
ENV TOKEN_TTL=6

EXPOSE 8080

CMD ["python", "app.py"]
