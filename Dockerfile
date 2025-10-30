FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY setup.py .
COPY src/ ./src/

# Install the package
RUN pip install -e .

# Create directories for files
RUN mkdir -p /app/shared /app/downloads /app/logs

# Expose default port
EXPOSE 5001

# Run the application
CMD ["p2p-chat", "--port", "5001", "--host", "0.0.0.0"]