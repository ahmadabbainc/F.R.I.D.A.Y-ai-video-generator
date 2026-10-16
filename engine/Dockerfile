# Optional: run Friday as your own HTTP engine on any host that runs Docker.
# docker build -t friday-engine engine && docker run -p 8000:8000 -e PEXELS_API_KEY=... friday-engine
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY friday ./friday

ENV FRIDAY_DATA_DIR=/data
VOLUME /data
EXPOSE 8000
CMD ["python", "-m", "friday", "serve", "--port", "8000"]
