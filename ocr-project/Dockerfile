FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential libffi-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv package manager
RUN python -m ensurepip && python -m pip install --upgrade pip \
    && pip install uv

# Copy only pyproject.toml first for caching
COPY pyproject.toml pyproject.toml

# Create uv environment and sync dependencies
RUN uv venv
RUN uv pip sync pyproject.toml

# Copy the rest of the code
COPY . .

EXPOSE 8000

# Run the app using uv (it uses the uv environment automatically)
CMD ["uv", "run", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
