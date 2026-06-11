FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN addgroup --system abs && adduser --system --ingroup abs absuser

# Install runtime dependencies
RUN pip install --no-cache-dir "mcp[cli]>=1.0" "httpx>=0.27" "uvicorn>=0.30" "starlette>=0.40"

# Copy source onto the Python path
COPY src/ ./src/
ENV PYTHONPATH=/app/src

# Switch to non-root
USER absuser

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

CMD ["python", "-m", "abs_librarian"]
