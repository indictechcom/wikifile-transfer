import os

from celery import Celery

CELERY_DEFAULT_QUEUE = "wikifile-transfer"
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0')

app = Celery(
    'tasks',
    broker=CELERY_BROKER_URL,
    backend=CELERY_BROKER_URL
)

app.conf.update( 
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)

if __name__ == '__main__': 
    app.start()