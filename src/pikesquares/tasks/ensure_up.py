from uwsgi_tasks import (
    task,
    SPOOL_OK,
    TaskExecutor,
)
print("I am a pikesquares.task")

@task(
    executor=TaskExecutor.SPOOLER,
    retry_count=3,
    retry_timeout=5,
)
def services_up():

    print("services_up")

    return SPOOL_OK
