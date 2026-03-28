from celery import Celery

from logger import get_logger
from celery.signals import task_failure, task_retry
from config import CELERY_BROKER_URL, CELERY_RESULT_EXPIRES, PRODUCTION
 
log = get_logger(__name__)

# Use environment variables
PRODUCTION = False
# CELERY_BROKER_URL = 'redis://redis:6379/0'
# CELERY_DEFAULT_QUEUE = "wikifile-transfer"


# if PRODUCTION:
#     REDIS_PASSWORD=''
#     REDIS_HOST='tools-redis.svc.eqiad.wmflabs'
#     REDIS_PORT='6379'
#     REDIS_DB=0

#     REDIS_URL = ':%s@%s:%s/%d' % (
#             REDIS_PASSWORD,
#             REDIS_HOST,
#             REDIS_PORT,
#             REDIS_DB)

#     CELERY_BROKER_URL = 'redis://' + REDIS_URL

app = Celery(
    'tasks',
    broker=CELERY_BROKER_URL,
    backend=CELERY_BROKER_URL
)

app.conf.update( 
    # result_expires=3600,
    result_expires=CELERY_RESULT_EXPIRES,
    broker_connection_retry_on_startup=True,
)


log.info(
    "Celery app initialised",
    extra={"broker": CELERY_BROKER_URL, "production": PRODUCTION},
)
 
# ── Global task-failure signal: log every unhandled task error ────────────────
#  fires automatically every time any task fails 
# — without you having to add error handling inside each individual task
@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    log.error(
        "Task failed",
        exc_info=True,
        extra={
            "task_name": sender.name,
            "task_id": task_id,
            "exception_type": type(exception).__name__,
            "exception": str(exception),
        },
    )
 
 
@task_retry.connect
def on_task_retry(sender, request, reason, einfo, **kw):
    log.warning(
        "Task retrying",
        extra={
            "task_name": sender.name,
            "task_id": request.id,
            "reason": str(reason),
            "retries": request.retries,
        },
    )
    
    
if __name__ == '__main__': 
    app.start()