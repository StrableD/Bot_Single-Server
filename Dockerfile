# Use the official Python image from the Docker Hub
FROM python:3.10-slim as base
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
FROM base as test
# Install testing tools
RUN pip install --no-cache-dir pytest pytest-asyncio ruff
# Run syntax/linter checks
RUN ruff check . --select=E9,F63,F7,F82
# Run the automated test suite! If tests fail, the Docker build fails here.
RUN pytest tests/

# --- PRODUCTION STAGE ---
FROM test as final
# Set the entrypoint command
CMD ["python", "launcher.py"]
