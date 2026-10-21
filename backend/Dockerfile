FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --no-cache-dir uv && uv pip install --system .
EXPOSE 8000
CMD ["uvicorn", "rendercart.main:app", "--host", "0.0.0.0", "--port", "8000"]
