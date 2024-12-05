FROM ubuntu

# Päivitä ja asenna tarvittavat riippuvuudet
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-venv \
    curl \
    build-essential \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y \
    && . $HOME/.cargo/env \
    && rustup target add wasm32-wasi \
    && ln -s $HOME/.cargo/bin/* /usr/local/bin/

# Työkansio kontissa
WORKDIR /app

# Kopioi vain requirements.txt ensin
COPY requirements.txt .

# Asenna Python-riippuvuudet
RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Kopioi kaikki tiedostot rakennuskontekstista
COPY . .

# Aseta PYTHONPATH niin, että `valmis/app` löytyy
ENV PYTHONPATH=/app/flask

# Avaa Flaskin käyttämä portti
EXPOSE 8080

# Käynnistä `__main__.py` moduulina
CMD ["bash", "-c", ". venv/bin/activate && python3 -m app"]