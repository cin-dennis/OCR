FROM python:3.13-slim

RUN apt-get update && apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync

COPY . .

EXPOSE 8000

RUN uv run alembic --version

COPY ./app ./app
COPY ./alembic ./alembic
COPY ./alembic.ini ./alembic.ini

CMD uv run alembic upgrade head

CMD ["uv", "run", "python", "app/main.py"]
