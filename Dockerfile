FROM python:3.12-slim AS builder

# Build ps3netsrv from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential meson ninja-build pkg-config libmbedtls-dev \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/aldostools/webMAN-MOD.git /tmp/webman \
 && cd /tmp/webman/_Projects_/ps3netsrv \
 && make -f Makefile.linux \
 && cp ps3netsrv /usr/local/bin/ps3netsrv \
 && chmod +x /usr/local/bin/ps3netsrv

# --- Final image ---
FROM python:3.12-slim

# Copy ps3netsrv binary
COPY --from=builder /usr/local/bin/ps3netsrv /usr/local/bin/ps3netsrv

# Install runtime deps for ps3netsrv (mbedtls)
RUN apt-get update && apt-get install -y --no-install-recommends libmbedtls-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

EXPOSE 5000
EXPOSE 38008

CMD ["python", "app.py"]
