# syntax=docker/dockerfile:1
# Security governance API and worker. Small on purpose: no ML stack here.
FROM python:3.11-slim

WORKDIR /srv
RUN useradd --system --uid 10001 govern
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY alembic.ini .
COPY migrations/ migrations/
COPY govern/ govern/
COPY docker-entrypoint.sh /usr/local/bin/
RUN mkdir -p /srv/evidence && chown govern /srv/evidence

USER govern
ENV GOVERN_EVIDENCE_DIR=/srv/evidence PYTHONUNBUFFERED=1
EXPOSE 8100
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "govern.main:app", "--host", "0.0.0.0", "--port", "8100", "--proxy-headers", "--forwarded-allow-ips", "*"]
