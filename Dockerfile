FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (needed for ChromaDB's SQLite/hnswlib C-extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch (CPU only) first to keep the image small and build fast.
# Downloading CUDA binaries for a CPU inferencing gateway adds 3GB of bloat.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# Set environment variables for thread safety (prevents macOS/Linux deadlocks)
ENV TOKENIZERS_PARALLELISM=false
ENV OMP_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

