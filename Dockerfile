FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build tools for scientific libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose default HTTP port
EXPOSE 8000

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Run FastAPI with uvicorn
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
