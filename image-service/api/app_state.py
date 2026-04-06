from logging_config import setup_logging
from task_queue import create_celery_app

from api.auth import APIKeyAuth
from api.models import RedisJobStore
from api.storage import R2Storage
from api.usage import UsageTracker

logger = setup_logging()
api_auth = APIKeyAuth()
redis_store = RedisJobStore()
storage = R2Storage()
usage_tracker = UsageTracker()
celery = create_celery_app("rendercart-api")
