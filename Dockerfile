FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source repository
COPY . .
RUN pip install --no-cache-dir -e .

EXPOSE 8000

# Uses shell expansion to bind to Render's dynamic $PORT (defaulting to 8000)
CMD ["sh", "-c", "flakeforge serve --host 0.0.0.0 --port ${PORT:-8000}"]
