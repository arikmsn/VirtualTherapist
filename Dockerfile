FROM python:3.11-slim

# System deps: libpq for psycopg2, gcc for some wheels
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer-cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir psycopg2-binary

# Copy application code
COPY . .

# Writable logs directory (stdout preferred in production, this is a fallback)
RUN mkdir -p logs

EXPOSE 8000

# Run migrations then start the server.
# PORT is injected by Render (and most container platforms); default to 8000 locally.
CMD python -m alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
