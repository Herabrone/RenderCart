from fastapi import FastAPI
from celery import Celery

app = FastAPI()

celery = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/generate")
def generate(prompt: str = "a product on a clean white background"):
    task = celery.send_task("worker.generate_image", args=[prompt])
    return {"job_id": task.id}

@app.get("/job/{job_id}")
def get_job(job_id: str):
    result = celery.AsyncResult(job_id)
    return {
        "status": result.status,
        "result": result.result
    }
