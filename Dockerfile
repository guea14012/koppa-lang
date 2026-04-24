## ── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY . .

# Install build tools + create wheel
RUN pip install --no-cache-dir build && python -m build --wheel

## ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="KOPPA"
LABEL org.opencontainers.image.description="Advanced Pentesting Domain-Specific Language"
LABEL org.opencontainers.image.source="https://github.com/YOUR_USERNAME/koppa-lang"
LABEL org.opencontainers.image.licenses="MIT"

# Install from wheel (no build tools in final image)
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Copy stdlib and examples
COPY stdlib/ /usr/local/lib/koppa/stdlib/
COPY examples/ /usr/local/lib/koppa/examples/

# Optional: install common pentest tools
# RUN apt-get update && apt-get install -y --no-install-recommends nmap curl && rm -rf /var/lib/apt/lists/*

WORKDIR /scripts

ENTRYPOINT ["koppa"]
CMD ["repl"]
