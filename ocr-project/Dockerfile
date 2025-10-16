FROM python:3.13-slim AS build

RUN apt-get update && apt-get install -y curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-install-project

FROM python:3.13-slim AS runtime

WORKDIR /app

COPY --from=build /root/.local/bin/uv /usr/local/bin/uv

COPY --from=build /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY . .

EXPOSE 8000

CMD ["uv", "run", "python", "main.py"]
