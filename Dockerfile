FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file bot
COPY searcher/ ./searcher/
COPY dashboard/ ./dashboard/

# Jalankan bot
CMD ["python3", "searcher/main.py", "--live"]
