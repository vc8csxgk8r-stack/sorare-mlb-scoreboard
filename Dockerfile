FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

VOLUME ["/data"]

EXPOSE 8501
EXPOSE 8502

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health && curl -f http://localhost:8502/api/health || exit 1

COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
