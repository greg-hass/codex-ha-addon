ARG BUILD_FROM
FROM ${BUILD_FROM}

WORKDIR /app

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv \
    nodejs \
    npm \
    gcc \
    musl-dev \
    libffi-dev

COPY requirements.txt .
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && npm install -g @openai/codex@0.114.0 \
    && codex --version

COPY app/ ./app/
COPY run.sh /run.sh

RUN chmod a+x /run.sh

RUN mkdir -p /data/.codex /share/codex

ENV PATH="/opt/venv/bin:${PATH}"

EXPOSE 8000

CMD [ "/run.sh" ]
