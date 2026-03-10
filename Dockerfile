FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user and set permissions
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Switch to non-root user
USER appuser

# Health check with timeout and status validation
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; r = requests.get('http://localhost:8080/_stcore/health', timeout=5); r.raise_for_status()" || exit 1

# Run startup script then streamlit
CMD ["sh", "-c", "python startup.py && streamlit run streamlit_app/app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true"]
