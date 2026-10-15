FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY pyproject.toml ./
COPY apps/api ./apps/api
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home crawlops
COPY migrations ./migrations
COPY alembic.ini ./
RUN mkdir -p /data && chown crawlops:crawlops /data
USER crawlops
CMD ["uvicorn", "crawlops.main:app", "--host", "0.0.0.0", "--port", "8000"]
