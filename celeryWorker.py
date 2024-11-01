from celery import Celery

# Use environment variables
PRODUCTION = False
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_DEFAULT_QUEUE = "wikifile-transfer"


if PRODUCTION:
    REDIS_PASSWORD=''
    REDIS_HOST='tools-redis.svc.eqiad.wmflabs'
    REDIS_PORT='6379'
    REDIS_DB=0

    REDIS_URL = ':%s@%s:%s/%d' % (
            REDIS_PASSWORD,
            REDIS_HOST,
            REDIS_PORT,
            REDIS_DB)

    CELERY_BROKER_URL = 'redis://' + REDIS_URL

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