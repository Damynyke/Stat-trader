FROM python:3.14-slim

# Set environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Expose port
EXPOSE 8000

# Run with gunicorn + uvicorn worker for production
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main_production:app", "--bind", "0.0.0.0:8000", "--workers", "2"]
