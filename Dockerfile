FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install uv

RUN uv sync --frozen

ENV PYTHONPATH=/app/src:/app/clients/python

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.mail_client_service.src.mail_client_service.app:app", "--host", "0.0.0.0", "--port", "8000"]

