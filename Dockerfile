
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source only (frontend not needed in image)
COPY backend/src ./src

# Expose port 8000 (default for Uvicorn)
EXPOSE 8000

# Health check to verify the application is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs').read()" || exit 1

# Run the FastAPI application with Uvicorn
CMD ["uvicorn", "src.fast_api:app", "--host", "0.0.0.0", "--port", "8000"]
