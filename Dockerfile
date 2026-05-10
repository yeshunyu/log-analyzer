FROM python:3.11-slim

WORKDIR /app

# Install deps first for better layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY backend/app.py .
COPY linux-os-log-analyzer.html .
COPY linux-os-log-collect.sh .

EXPOSE 5000

CMD ["python", "app.py"]
