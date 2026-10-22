FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY smartwaste_backend ./smartwaste_backend

CMD ["uvicorn", "smartwaste_backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
