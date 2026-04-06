import os

from celery import Celery
from kombu import Queue


TASK_QUEUES = (
    Queue("download"),
    Queue("preprocess"),
    Queue("generate"),
    Queue("upload"),
    Queue("status"),
)

TASK_ROUTES = {
    "worker.process_job": {"queue": "generate"},
    "tasks.download_input_image": {"queue": "download"},
    "tasks.preprocess_image": {"queue": "preprocess"},
    "tasks.generate_images": {"queue": "generate"},
    "tasks.upload_results": {"queue": "upload"},
    "tasks.update_job_status": {"queue": "status"},
}


def configure_celery(app: Celery) -> Celery:
    app.conf.task_queues = TASK_QUEUES
    app.conf.task_routes = TASK_ROUTES
    app.conf.task_default_queue = "generate"
    return app


def create_celery_app(name: str) -> Celery:
    app = Celery(
        name,
        broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    )
    return configure_celery(app)
