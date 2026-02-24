FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8787

CMD ["gunicorn", "server:app", \
     "--bind", "0.0.0.0:8787", \
     "--timeout", "1800", \
     "--workers", "2", \
     "--access-logfile", "-"]
