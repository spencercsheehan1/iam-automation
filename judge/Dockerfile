FROM python:3.12-slim

WORKDIR /app

# System deps: none needed beyond what python:slim ships — snowflake
# connector and cryptography wheels are pure-python/manylinux, no
# compiler toolchain required.

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY engine/ ./engine/
COPY sources/ ./sources/
COPY storage/ ./storage/
COPY policies/ ./policies/
COPY data/ ./data/

# Non-root user — no reason for this process to run as root.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)" || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
