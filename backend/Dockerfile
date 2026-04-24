FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts

RUN mkdir -p /app/data/chroma /app/data/regulations /app/logs/llm

EXPOSE 8000

CMD ["uvicorn", "src.mokn.main:app", "--host", "0.0.0.0", "--port", "8000"]
