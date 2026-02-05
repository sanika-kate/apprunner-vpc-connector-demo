FROM python:3.11-slim

WORKDIR /app

# Copy dependencies first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# App Runner listens on this port
EXPOSE 8080

# Correct way to start FastAPI app
CMD ["python", "main.py"]
