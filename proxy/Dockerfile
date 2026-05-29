# proxy/Dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies + runtime
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    python3 \
    python3-pip \
    python3-dev \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install psycopg2-binary (needs build deps)
RUN pip3 install --no-cache-dir psycopg2-binary

# Build 3proxy from source
RUN cd /tmp && \
    wget https://github.com/3proxy/3proxy/archive/refs/tags/0.9.4.tar.gz && \
    tar xzf 0.9.4.tar.gz && \
    cd 3proxy-0.9.4 && \
    make -f Makefile.Linux && \
    mkdir -p /usr/local/bin && \
    cp bin/3proxy /usr/local/bin/ && \
    chmod +x /usr/local/bin/3proxy && \
    cd / && \
    rm -rf /tmp/3proxy-0.9.4 /tmp/0.9.4.tar.gz

# Cleanup build dependencies (optional, reduces size)
RUN apt-get remove -y build-essential python3-dev libpq-dev gcc && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Create app dir and copy files
WORKDIR /app
COPY config_generator.py /app/
COPY entrypoint.sh /app/

# Make executable
RUN chmod +x /app/entrypoint.sh

# Create required directories
RUN mkdir -p /var/log/3proxy /etc/3proxy && \
    chown -R nobody:nogroup /var/log/3proxy /etc/3proxy || true

# Expose port
EXPOSE 3389

# Use entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
