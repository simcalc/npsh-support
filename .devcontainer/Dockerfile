# The OS image follows Ubuntu 24.04 security updates. The solver package has
# an exact version and checksum; this is not a bit-for-bit frozen OS image.
FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 git curl ca-certificates sudo gh && rm -rf /var/lib/apt/lists/*
USER vscode
