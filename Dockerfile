FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY zustaendigkeit.py mcp_server.py api.py ./
COPY quellen ./quellen

ENV PORT=8000 \
    ZF_VORLADEN=1 \
    ZF_CACHE_DIR=/data/cache \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)"

# Standard: MCP-Server. Für die HTTP-API stattdessen:
#   docker run ... zf-mcp uvicorn api:app --host 0.0.0.0 --port 8000
CMD ["python", "mcp_server.py"]
