FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy project metadata and source, then create a locked venv at build time.
COPY pyproject.toml uv.lock README.md ./
COPY app ./app

# Install `uv` and create the project's `.venv` according to the lockfile.
RUN pip install --no-cache-dir uv==0.11.8 \
    && uv sync --frozen

EXPOSE 8000

# Use uv's 'run' to execute uvicorn inside the created venv.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
