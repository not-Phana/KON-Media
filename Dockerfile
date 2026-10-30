# Production Dockerfile for KON Media & KON Search 1.1.0 Rei
# Optimized for 24/7 Cloud Hosting (Hugging Face Spaces, Render, Railway, Koyeb)

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8899 \
    HOST=0.0.0.0

# Install system dependencies: FFmpeg for audio extraction & stream merging, Node.js for yt-dlp, curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application backend, model packages, and prebuilt frontend SPA
COPY backend ./backend
COPY kon_search ./kon_search
COPY app_state ./app_state
COPY frontend/dist ./frontend/dist
COPY index.html .
COPY README.md .

# Create persistent state, download, and temporary directories
RUN mkdir -p /app/downloads /app/.cache/tmp /app/app_state

# Expose default port
EXPOSE 8899

# Run FastAPI production server
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
