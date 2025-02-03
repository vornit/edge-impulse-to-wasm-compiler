FROM ubuntu

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-venv \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y \
    && . $HOME/.cargo/env \
    && rustup update \
    && rustup target add wasm32-wasip1 \
    && ln -s $HOME/.cargo/bin/* /usr/local/bin/ \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/flask

EXPOSE 8080

CMD ["bash", "-c", ". venv/bin/activate && python3 -m app"]