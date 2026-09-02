FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy lockfile and pyproject first for layer caching —
# dependencies only reinstall when these files change
COPY pyproject.toml uv.lock ./

# Sync dependencies into the project virtualenv
RUN uv sync --frozen --no-dev

# Copy the rest of the source
COPY . .

# Train all ML artefacts and bake them into the image
RUN PYTHONIOENCODING=utf-8 uv run python train.py

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]