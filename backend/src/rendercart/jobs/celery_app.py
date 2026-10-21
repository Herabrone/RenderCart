from celery import Celery
from celery.schedules import crontab

from rendercart.core.config import get_settings

settings = get_settings()
broker = settings.celery_broker_url or settings.redis_url.rsplit("/", 1)[0] + "/1"
result_backend = settings.celery_result_backend or settings.redis_url.rsplit("/", 1)[0] + "/2"
app = Celery("rendercart", broker=broker, backend=result_backend)
app.autodiscover_tasks(["rendercart.jobs"])
app.conf.update(
    task_default_queue="cpu.default",
    task_queues=None,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "cleanup-expired-files-hourly": {
            "task": "rendercart.jobs.tasks.cleanup_expired",
            "schedule": crontab(minute=17),
        },
        "dispatch-paid-jobs-every-minute": {
            "task": "rendercart.jobs.tasks.dispatch_paid_jobs",
            "schedule": 60.0,
        },
        "expire-credit-lots-every-five-minutes": {
            "task": "rendercart.jobs.tasks.expire_credits",
            "schedule": 300.0,
        },
        "generate-recurring-invoices-every-minute": {
            "task": "rendercart.jobs.tasks.generate_recurring_invoices",
            "schedule": 60.0,
        },
        "generate-website-audit-schedules-every-minute": {
            "task": "rendercart.jobs.tasks.generate_website_audit_schedules",
            "schedule": 60.0,
        },
        "check-due-uptime-monitors-every-minute": {
            "task": "rendercart.jobs.tasks.check_due_uptime_monitors",
            "schedule": 60.0,
        },
        "check-domain-expiry-alerts-every-minute": {
            "task": "rendercart.jobs.tasks.check_due_domain_expiry_alerts",
            "schedule": 60.0,
        },
        "cleanup-expired-webhook-bins-every-five-minutes": {
            "task": "rendercart.jobs.tasks.cleanup_expired_webhook_bins",
            "schedule": 300.0,
        },
        "cleanup-expired-vault-items-every-five-minutes": {
            "task": "rendercart.jobs.tasks.cleanup_expired_vault_items",
            "schedule": 300.0,
        },
        "refresh-ecb-currency-rates-daily": {
            "task": "rendercart.jobs.tasks.refresh_currency_rates",
            "schedule": crontab(hour=16, minute=30),
        },
    },
)
