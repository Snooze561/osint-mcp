# Image Docker de osint-mcp.
#
# Une image contient tout ce qu'il faut pour faire tourner l'appli (Python,
# dépendances, code). On la construit une fois, puis on la lance partout de
# la même façon : sur ton PC, sur un serveur, chez quelqu'un d'autre...
#
#   docker build -t osint-mcp .
#   docker run --rm -p 127.0.0.1:8000:8000 osint-mcp
#
# Le plus simple reste docker compose (voir compose.yaml).

FROM python:3.13-slim

# uv, le même gestionnaire de projet que sur ton PC.
RUN pip install --no-cache-dir "uv==0.11.*"

WORKDIR /app

# 1. Les dépendances d'abord : Docker garde cette étape en cache tant que
#    pyproject.toml et uv.lock ne changent pas, ce qui accélère les reconstructions.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# 2. Puis le code de l'application.
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev

# On ne fait pas tourner l'appli en "root" : c'est une bonne pratique de sécurité.
RUN useradd --create-home osint && mkdir -p /data && chown osint /data
USER osint

ENV PATH="/app/.venv/bin:$PATH" \
    OSINT_MCP_DATA=/data \
    PYTHONUNBUFFERED=1

EXPOSE 8000 8001

# Par défaut : l'interface web. "0.0.0.0" = écouter à l'intérieur du conteneur ;
# c'est la ligne "ports" de compose.yaml qui décide qui peut y accéder.
CMD ["osint-web", "--host", "0.0.0.0", "--port", "8000", "--sans-navigateur"]
