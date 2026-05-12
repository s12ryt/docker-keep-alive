FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

RUN adduser --system --no-create-home appuser

COPY pyproject.toml ./
COPY app ./app
RUN chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["python", "-m", "app.main"]
