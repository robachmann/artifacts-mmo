# Use a lightweight Python image based on Alpine
FROM python:3.13-alpine

# Set environment variables to prevent Python from writing .pyc files and to buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies and build tools
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    make

# Create a working directory
WORKDIR /app

# Install Python dependencies
COPY src/common_layer/ /app/
RUN pip install --no-cache-dir -r requirements-websocket.txt

# Copy the application code
COPY src/websocket-container/ /app/

# Define the default command to run the application
CMD ["python", "app.py"]
