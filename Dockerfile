FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for chromadb, sentence-transformers, torch)
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch FIRST from the CPU wheel index. The default PyPI torch
# wheel pulls multi-GB CUDA packages (cudnn / cusparselt / cuda_toolkit) that
# blow up image size and time out on constrained networks. The demo runs on CPU,
# so CPU wheels are sufficient and ~10x smaller. `requirements.txt` lists
# `torch`/`torchvision` unpinned; once installed here, pip treats them as
# satisfied and skips re-install in the next step.
RUN pip install --no-cache-dir --retries 5 --timeout 180 \
    --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 180 -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY .env.example .env

# Health check — respect the PORT injected by the platform (Railway), fall back to 8000 locally.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000'))"

EXPOSE 8000

# Shell form so ${PORT} is expanded. Railway injects PORT; docker-compose has none, so it falls back to 8000.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
