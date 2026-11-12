FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY zustaendigkeit.py mcp_server.py ./
ENV PORT=8000 ZF_VORLADEN=1 ZF_CACHE_DIR=/data/cache
VOLUME /data
EXPOSE 8000
CMD ["python", "mcp_server.py"]
