FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# Longer timeout and more retries so a slow connection doesn't kill the build
RUN pip install --no-cache-dir --timeout=120 --retries=10 -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]