# Use the official Python image from the Docker Hub
FROM python:3.10-slim AS base
LABEL authors="david"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create and set the working directory inside the container
WORKDIR /app

# Install system dependencies (ffmpeg for music cog)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Create data directories if they don't exist
RUN mkdir -p /app/data/db /app/data/music_cache /app/config

# --- TEST STAGE ---
FROM base AS test
# Install testing tools
RUN pip install --no-cache-dir pytest pytest-asyncio ruff
# Run strict syntax/linter checks (Error, Fatal, Warning, Bugbear, Isort)
RUN ruff check . --select=E,F,W,B,I --extend-ignore=E501
# Run strict formatting enforcement (Build fails if code isn't perfectly formatted)
RUN ruff format . --check
# Run the automated test suite! If tests fail, the Docker build fails here.
ENV PYTHONPATH=/app
RUN python -m pytest tests/

# --- PRODUCTION STAGE ---
FROM test AS final
# Set the entrypoint command
CMD ["python", "launcher.py"]
