FROM ubuntu

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-venv \
    curl \
    build-essential \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y \
    && . $HOME/.cargo/env \
    && rustup target add wasm32-wasi \
    && ln -s $HOME/.cargo/bin/* /usr/local/bin/

WORKDIR /app

COPY requirements.txt .

RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/flask

EXPOSE 8080

CMD ["bash", "-c", ". venv/bin/activate && python3 -m app"]