FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# Uses the app's real DB-backed /health endpoint (not just "is the port
# open") so an orchestrator restarts a container that's up but can't
# reach its database, not just one that's fully down. curl is present
# via the python:3.11-slim base's apt layer above pulling in ca-certificates
# transitively is not guaranteed, so install curl explicitly for this.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
