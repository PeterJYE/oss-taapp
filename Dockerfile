FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install uv

RUN uv sync --frozen

ENV PYTHONPATH=/app/src:/app/clients/python

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn src.mail_client_service.src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

