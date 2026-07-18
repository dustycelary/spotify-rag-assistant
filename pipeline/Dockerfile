FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --default-timeout=100 --retries 5 -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

CMD ["python", "pipeline/ingest.py"]
