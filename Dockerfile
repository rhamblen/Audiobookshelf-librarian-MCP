FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN addgroup --system abs && adduser --system --ingroup abs absuser

# Install dependencies first (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[all]" 2>/dev/null || pip install --no-cache-dir .

# Copy source
COPY src/ ./src/

# Switch to non-root
USER absuser

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

CMD ["python", "-m", "abs_librarian"]
