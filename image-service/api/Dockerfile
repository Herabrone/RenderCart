FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY configs ./configs
COPY worker ./worker
COPY business_presets.py ./
COPY config.py ./
COPY logging_config.py ./
COPY model_loader.py ./
COPY task_queue.py ./
COPY url_safety.py ./
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn api.main:app --host 0.0.0.0 --port 8000"]
