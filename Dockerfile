FROM python:3.11-slim

WORKDIR /app

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install uv and sync dependencies
RUN pip install uv

RUN uv sync --frozen

ENV PYTHONPATH=/app/src

EXPOSE 8000

# Run the OpenAI client service
CMD ["sh", "-c", "uv run uvicorn openai_client_service.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

