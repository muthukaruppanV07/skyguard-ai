# SkyGuard AI — single-service image (Hugging Face Spaces / any Docker host).
# Spaces expects the app on port 7860 ($PORT).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY frontend/package.json frontend/package-lock.json frontend/
RUN npm --prefix frontend install --no-audit --no-fund

COPY . .
RUN npm --prefix frontend run build

EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
